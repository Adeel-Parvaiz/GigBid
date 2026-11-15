"""Official Upwork MCP through the common port. Tool mappings are schema-reviewed, never guessed."""
import asyncio
import hashlib
import json
import time
from contextvars import ContextVar
from urllib.parse import urlparse

import jsonschema

from agent.marketplace_context import approved_write, marketplace_user
from agent.marketplace_port import MarketplaceError
from mcp_servers.marketplace.adapters.gigsim import render, select

READS = {'search_jobs', 'get_job', 'get_client_history', 'get_connects_balance', 'list_threads', 'list_messages'}
WRITES = {'proposal_draft', 'message_draft'}
read_times = {}
marketplace_binding: ContextVar[str | None] = ContextVar('marketplace_binding', default=None)


def validate_mapping(mapping, catalog):
    schemas = {t['name']: t for t in catalog}
    if set(mapping) - READS - WRITES:
        raise ValueError('Unknown marketplace operation')
    for operation, entry in mapping.items():
        if operation == 'message_draft' and entry.get('source') == 'local_message_draft':
            tool = schemas.get('upwork__send_message', {})
            if tool.get('annotations', {}).get('readOnlyHint') is not False:
                raise ValueError('Official send-message contract must be discovered before staging message drafts')
            continue
        if operation == 'get_client_history' and entry.get('source') == 'job_detail_client_record':
            if mapping.get('get_job', {}).get('normalizer') != 'official_job_detail':
                raise ValueError('Client record cache requires the verified official job detail mapping')
            continue
        tool = schemas.get(entry.get('tool'))
        if not tool:
            raise ValueError(f'{operation}: select a tool from the authenticated discovery catalog')
        annotations = tool.get('annotations', {})
        if operation in READS and annotations.get('readOnlyHint') is not True:
            raise ValueError(f'{operation}: provider must explicitly annotate the mapped tool as read-only')
        if operation in WRITES:
            official_preview = (operation == 'proposal_draft' and entry.get('tool') == 'upwork__manage_proposals'
                                and entry.get('effect') == 'official_proposal_preview'
                                and 'Returns a preview' in tool.get('description', '')
                                and 'confirm_preview' in tool.get('description', ''))
            if official_preview:
                continue
            if entry.get('effect') != 'draft' or annotations.get('readOnlyHint') is not False or annotations.get('destructiveHint') is not False:
                raise ValueError(f'{operation}: only an explicitly non-destructive draft tool can be mapped')
            if not entry.get('confirmation_pointer'):
                raise ValueError(f'{operation}: map the platform confirmation URL')
        if not isinstance(entry.get('arguments', {}), dict):
            raise ValueError('Tool arguments must be an object template')


class UpworkLiveAdapter:
    def __init__(self, oauth, user):
        self.oauth, self.user = oauth, user

    async def _call(self, operation, **arguments):
        mapping = self.oauth.vault.get(self.user, 'mapping', {})
        catalog = self.oauth.vault.get(self.user, 'catalog', [])
        validate_mapping(mapping, catalog)
        entry = mapping.get(operation)
        if not entry:
            raise MarketplaceError('upwork_capability_unmapped', operation)
        if entry.get('source') == 'job_detail_client_record':
            record = self.oauth.vault.get(self.user, 'client:' + arguments['client_id'])
            if record is None:
                raise MarketplaceError('upwork_contract_error', 'Load job details before client history')
            return record
        arguments['account'] = self.oauth.vault.get(self.user, 'account', {})
        if entry.get('normalizer') == 'official_job_search':
            arguments['limit'] = min(10, max(1, int(arguments.get('limit', 10))))
            arguments['query'] = arguments.get('query') or ''
        tool = next(t for t in catalog if t['name'] == entry['tool'])
        try:
            args = render(entry.get('arguments', {}), arguments)
            jsonschema.validate(args, tool['inputSchema'])
        except (KeyError, TypeError, jsonschema.ValidationError) as error:
            raise MarketplaceError('upwork_contract_error', 'Arguments do not match the discovered tool schema') from error
        if operation in WRITES and not approved_write.get():
            raise MarketplaceError('approval_required', 'Approve the draft in GigBid first')
        # Cache only identical reads for 60 seconds; no external scheduled read loop is enabled by default.
        fingerprint = hashlib.sha256(json.dumps([operation, args], sort_keys=True).encode()).hexdigest()
        cache_key = (self.user, self.oauth.vault.get(self.user, 'binding'), fingerprint)
        cached = read_times.get(cache_key)
        if operation in READS and cached and time.monotonic() - cached[0] < 60:
            return cached[1]
        last_error = None
        for attempt in range(2 if operation in READS else 1):
            try:
                async with asyncio.timeout(35):
                    async with self.oauth.client(self.user).session('upwork') as session:
                        result = await session.call_tool(entry['tool'], args)
                if result.isError:
                    raise MarketplaceError('upwork_tool_error', 'Upwork rejected the call; inspect your account before retrying a write')
                data = result.structuredContent
                if data is None:
                    texts = [c.text for c in result.content if getattr(c, 'type', None) == 'text']
                    data = json.loads(texts[0]) if len(texts) == 1 else None
                if data is None:
                    raise MarketplaceError('upwork_contract_error', 'Map a structured provider response')
                value = select(data, entry.get('response_pointer', ''))
                if entry.get('normalizer'):
                    from mcp_servers.marketplace.adapters.upwork_normalize import normalize
                    value = normalize(entry['normalizer'], value, self.oauth.vault, self.user, arguments)
                # Optional normalization of provider field names onto MarketplacePort fields.
                if entry.get('output') is not None:
                    value = [render(entry['output'], {'result': row}) for row in value] if isinstance(value, list) else render(entry['output'], {'result': value})
                if operation in READS:
                    read_times[cache_key] = (time.monotonic(), value)
                    if len(read_times) > 1024:
                        read_times.pop(next(iter(read_times)))
                return value
            except MarketplaceError:
                raise
            except Exception as error:
                last_error = error
                if attempt == 0 and operation in READS:
                    await asyncio.sleep(.3)
        raise MarketplaceError('marketplace_unavailable', 'Upwork call failed; reconnect or check the account before retrying') from last_error

    async def _draft_write(self, operation, payload, key):
        if self.oauth.vault.get(self.user, 'mode') == 'upwork_readonly':
            raise MarketplaceError('upwork_readonly', 'This live connection is restricted to reads')
        if not approved_write.get():
            raise MarketplaceError('approval_required')
        lock = self.oauth.locks.setdefault(self.user, asyncio.Lock())
        async with lock:
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            kind = 'write:' + operation + ':' + key
            old = self.oauth.vault.get(self.user, kind)
            if old:
                if old['fingerprint'] != fingerprint:
                    raise MarketplaceError('idempotency_conflict')
                if old.get('result'):
                    return {**old['result'], 'replayed': True}
                raise MarketplaceError('upwork_write_uncertain', 'Check pending drafts and Connects on Upwork; automatic retry is disabled')
            # Durable intent before network I/O. A crash/timeout never silently repeats the provider write.
            if not self.oauth.vault.claim(self.user, kind, {'fingerprint': fingerprint}):
                raise MarketplaceError('upwork_write_uncertain', 'Another process already started this write')
            entry = self.oauth.vault.get(self.user, 'mapping', {}).get(operation, {})
            if entry.get('effect') == 'official_proposal_preview' or entry.get('source') == 'local_message_draft':
                from mcp_servers.marketplace.adapters.upwork_actions import prepare
                result = await prepare(self, operation, payload, key)
                self.oauth.vault.put(self.user, kind, {'fingerprint': fingerprint, 'result': result})
                return result
            value = await self._call(operation, payload=payload, idempotency_key=key)
            url = select(value, entry['confirmation_pointer'])
            parsed = urlparse(url)
            if parsed.scheme != 'https' or not (parsed.hostname == 'upwork.com' or (parsed.hostname or '').endswith('.upwork.com')):
                raise MarketplaceError('upwork_contract_error', 'Provider did not return an official Upwork confirmation URL')
            result = {'status': 'awaiting_platform_confirmation', 'confirmation_url': url, 'replayed': False}
            self.oauth.vault.put(self.user, kind, {'fingerprint': fingerprint, 'result': result})
            return result

    async def search_jobs(self, query=None, limit=20):
        return await self._call('search_jobs', query=query, limit=limit)

    async def get_job(self, job_id):
        return await self._call('get_job', job_id=job_id)

    async def get_client_history(self, client_id):
        return await self._call('get_client_history', client_id=client_id)

    async def get_connects_balance(self):
        return await self._call('get_connects_balance')

    async def list_threads(self):
        return await self._call('list_threads')

    async def list_messages(self, thread_id):
        return await self._call('list_messages', thread_id=thread_id)

    async def create_proposal_draft(self, payload, idempotency_key, dry_run=False):
        job = await self.get_job(payload['job_id'])
        if dry_run:
            return {'dry_run': True, 'would_send': payload, 'connects_cost': job['connects_cost'],
                    'requires_platform_confirmation': True}
        if self.oauth.vault.get(self.user, 'mode') == 'upwork_readonly':
            raise MarketplaceError('upwork_readonly', 'This live connection is restricted to reads')
        if not approved_write.get():
            raise MarketplaceError('approval_required')
        # Internal staging only. The subsequent port submit maps to a provider DRAFT, never final submission.
        draft_id = 'upwork-draft-' + hashlib.sha256(idempotency_key.encode()).hexdigest()[:20]
        old = self.oauth.vault.get(self.user, draft_id)
        if old and old != payload:
            raise MarketplaceError('idempotency_conflict')
        self.oauth.vault.put(self.user, draft_id, payload)
        return {'draft_id': draft_id, 'status': 'draft', 'connects_cost': job['connects_cost'], 'replayed': old is not None}

    async def submit_proposal(self, draft_id, idempotency_key):
        payload = self.oauth.vault.get(self.user, draft_id)
        if not payload:
            raise MarketplaceError('draft_not_found')
        result = await self._draft_write('proposal_draft', payload, idempotency_key)
        return {**result, 'draft_id': draft_id, 'connects_spent': 0}

    async def send_message(self, thread_id, text, idempotency_key):
        result = await self._draft_write('message_draft', {'thread_id': thread_id, 'text': text}, idempotency_key)
        return {**result, 'thread_id': thread_id, 'message_id': 'pending-platform-confirmation'}

    async def confirm_platform_action(self, action_id, review_hash):
        if not approved_write.get() or self.oauth.vault.get(self.user, 'mode') != 'upwork':
            raise MarketplaceError('approval_required', 'Explicit platform confirmation is required in live mode')
        from mcp_servers.marketplace.adapters.upwork_actions import confirm
        return await confirm(self, action_id, review_hash)


class RoutedMarketplacePort:
    """One common port, selected per authenticated user; never a global provider switch."""
    def __init__(self, fallback, oauth):
        self.fallback, self.oauth = fallback, oauth

    def __getattr__(self, name):
        if name not in READS | {'create_proposal_draft', 'submit_proposal', 'send_message', 'confirm_platform_action'}:
            return getattr(self.fallback, name)

        async def call(*args, **kwargs):
            user = marketplace_user.get()
            live = user and self.oauth.vault.get(user, 'mode') in {'upwork', 'upwork_readonly'}
            expected = marketplace_binding.get()
            binding = self.binding(user)
            if expected and expected != binding:
                raise MarketplaceError('marketplace_changed', 'Marketplace connection changed; start a new run and review its preview')
            port = UpworkLiveAdapter(self.oauth, user) if live else self.fallback
            return await getattr(port, name)(*args, **kwargs)
        return call

    def binding(self, user):
        if user and self.oauth.vault.get(user, 'mode') in {'upwork', 'upwork_readonly'}:
            return 'upwork:' + str(self.oauth.vault.get(user, 'binding', 'disconnected'))
        return 'simulator'
