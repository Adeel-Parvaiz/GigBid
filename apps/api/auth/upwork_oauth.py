"""Official MCP OAuth authorization, encrypted storage and authenticated schema discovery."""
import asyncio
import json
import logging
import os
import secrets
from urllib.parse import parse_qs, urlparse

from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata, OAuthMetadata, ProtectedResourceMetadata

from apps.api.auth.oauth_store import OAuthVault, UserOAuthStorage

UPWORK_URL = 'https://mcp.upwork.com/mcp'


class OAuthLogFilter(logging.Filter):
    def filter(self, record):
        # SDK exception messages may include a provider's token-endpoint response body.
        if record.levelno >= logging.WARNING:
            record.msg, record.args, record.exc_info, record.exc_text = 'MCP OAuth operation failed; reconnect from Settings.', (), None, None
        return True


class PersistentOAuthProvider(OAuthClientProvider):
    """Hydrate expiry and discovered metadata when a new MCP HTTP session is opened."""
    async def _initialize(self):
        await super()._initialize()
        storage = self.context.storage
        token = storage.vault.get(storage.user, 'tokens')
        if token and token.get('expires_at') is not None:
            self.context.token_expiry_time = token['expires_at'] or -1
        metadata = storage.vault.get(storage.user, 'oauth_metadata', {})
        if metadata.get('server_url') == self.context.server_url:
            if metadata.get('oauth'):
                self.context.oauth_metadata = OAuthMetadata.model_validate(metadata['oauth'])
            if metadata.get('resource'):
                self.context.protected_resource_metadata = ProtectedResourceMetadata.model_validate(metadata['resource'])
            self.context.auth_server_url = metadata.get('auth_server_url')


class UpworkOAuth:
    def __init__(self, vault=None, server_url=UPWORK_URL, callback_url=None):
        self.vault = vault or OAuthVault()
        self.server_url = server_url
        self.callback_url = callback_url or os.environ.get('UPWORK_CALLBACK_URL', 'http://127.0.0.1:8000/connections/upwork/callback')
        self.pending = {}
        self.locks = {}
        logger = logging.getLogger('mcp.client.auth.oauth2')
        if not any(isinstance(f, OAuthLogFilter) for f in logger.filters):
            logger.addFilter(OAuthLogFilter())

    def provider(self, user, redirect=None, callback=None):
        async def reconnect(url):
            raise RuntimeError('Upwork authorization expired; reconnect from Settings')
        return PersistentOAuthProvider(server_url=self.server_url,
                                   client_metadata=OAuthClientMetadata(redirect_uris=[self.callback_url], client_name='GigBid', token_endpoint_auth_method='none'),
                                   storage=UserOAuthStorage(self.vault, user), redirect_handler=redirect or reconnect,
                                   callback_handler=callback, timeout=300)

    def client(self, user, provider=None):
        return MultiServerMCPClient({'upwork': {'transport': 'streamable_http', 'url': self.server_url,
                                               'auth': provider or self.provider(user), 'timeout': 20,
                                               'sse_read_timeout': 30}}, handle_tool_errors=False)

    async def discover(self, user, provider=None):
        provider = provider or self.provider(user)
        async with self.client(user, provider).session('upwork') as session:
            catalog, cursor = [], None
            for _ in range(20):
                page = await session.list_tools(cursor=cursor)
                catalog.extend(t.model_dump(mode='json', exclude_none=True) for t in page.tools)
                cursor = page.nextCursor
                if not cursor:
                    break
            else:
                raise RuntimeError('Upwork tool listing exceeded pagination bound')
        previous = self.vault.get(user, 'catalog')
        if previous is not None and previous != catalog:
            self.vault.delete(user, 'mapping')
            self.vault.put(user, 'mode', 'simulator')
        self.vault.put(user, 'catalog', catalog)
        context = provider.context
        self.vault.put(user, 'oauth_metadata', {'server_url': self.server_url, 'auth_server_url': context.auth_server_url,
                       'oauth': context.oauth_metadata.model_dump(mode='json') if context.oauth_metadata else None,
                       'resource': context.protected_resource_metadata.model_dump(mode='json') if context.protected_resource_metadata else None})
        return catalog

    async def start(self, user):
        old = self.pending.get(user)
        if old and not old['task'].done():
            old['task'].cancel()
        loop = asyncio.get_running_loop()
        pending = {'redirect': loop.create_future(), 'callback': loop.create_future(), 'state': None, 'status': 'starting'}

        async def redirect(url):
            parsed = urlparse(url)
            # Production only uses the official endpoint; local OAuth fixtures are constructor-injected in tests.
            official = self.server_url == UPWORK_URL and parsed.scheme == 'https' and (parsed.hostname == 'upwork.com' or (parsed.hostname or '').endswith('.upwork.com'))
            local_fixture = self.server_url != UPWORK_URL and parsed.hostname == urlparse(self.server_url).hostname and parsed.scheme == urlparse(self.server_url).scheme
            if not (official or local_fixture):
                raise RuntimeError('Authorization endpoint is outside the configured provider origin')
            pending['state'] = parse_qs(parsed.query)['state'][0]
            pending['status'] = 'awaiting_authorization'
            if not pending['redirect'].done():
                pending['redirect'].set_result(url)

        async def callback():
            return await asyncio.wait_for(pending['callback'], 300)

        async def flow():
            try:
                await asyncio.wait_for(self.discover(user, self.provider(user, redirect, callback)), 330)
                if self.server_url == UPWORK_URL:
                    await self.configure_official_account(user)
                self.vault.put(user, 'binding', secrets.token_hex(16))
                pending['status'] = 'connected'
                if not pending['redirect'].done():
                    pending['redirect'].set_result(None)
            except asyncio.CancelledError:
                pending['status'] = 'cancelled'
                raise
            except Exception:
                # Provider errors can contain tokens, codes or request bodies; never return their text.
                pending['status'] = 'failed'
                if not pending['redirect'].done():
                    pending['redirect'].set_result(None)

        pending['task'] = asyncio.create_task(flow())
        self.pending[user] = pending
        url = await asyncio.wait_for(asyncio.shield(pending['redirect']), 25)
        return {'authorization_url': url, 'status': pending['status']}

    async def configure_official_account(self, user):
        from mcp_servers.marketplace.adapters.upwork_live import validate_mapping
        from mcp_servers.marketplace.adapters.upwork_normalize import official_read_mapping
        if self.server_url != UPWORK_URL:
            raise ValueError('Automatic Upwork mapping only targets the official provider')
        async with self.client(user).session('upwork') as session:
            result = await session.call_tool('upwork__list_accounts', {})
        if result.isError:
            raise ValueError('Upwork account discovery failed')
        data = result.structuredContent
        if data is None:
            data = json.loads(next(c.text for c in result.content if getattr(c, 'type', None) == 'text'))
        accounts = [a for a in data.get('accounts', []) if a.get('role') == 'TALENT']
        if len(accounts) != 1:
            self.vault.delete(user, 'account')
            self.vault.delete(user, 'mapping')
            self.vault.put(user, 'mode', 'simulator')
            return False
        mapping = official_read_mapping()
        catalog = self.vault.get(user, 'catalog', [])
        names = {t['name'] for t in catalog}
        if {'upwork__manage_proposals', 'upwork__confirm_preview', 'upwork__list_freelancer_proposals'} <= names:
            mapping['proposal_draft'] = {'tool': 'upwork__manage_proposals', 'effect': 'official_proposal_preview'}
        if 'upwork__send_message' in names:
            mapping['message_draft'] = {'source': 'local_message_draft'}
        validate_mapping(mapping, catalog)
        self.vault.put(user, 'account', {'org_uid': accounts[0]['org_uid'], 'role': 'TALENT'})
        self.vault.put(user, 'mapping', mapping)
        return True

    async def finish(self, state, code):
        for _user, pending in self.pending.items():
            if pending['state'] and secrets.compare_digest(pending['state'], state):
                if pending['callback'].done() or pending['task'].done():
                    raise ValueError('Authorization is expired or already used')
                pending['callback'].set_result((code, state))
                pending['state'] = None
                await asyncio.wait_for(asyncio.shield(pending['task']), 30)
                return pending['status'] == 'connected'
        raise ValueError('Unknown or expired OAuth state; reconnect from Settings')

    def disconnect(self, user):
        pending = self.pending.pop(user, None)
        if pending and not pending['task'].done():
            pending['task'].cancel()
        for kind in ['tokens', 'client', 'catalog', 'mapping', 'mode', 'binding', 'oauth_metadata', 'account']:
            self.vault.delete(user, kind)

    async def close(self):
        tasks = [p['task'] for p in self.pending.values() if not p['task'].done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
