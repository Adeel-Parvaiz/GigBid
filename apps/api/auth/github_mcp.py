"""Per-user connection to GitHub's official read-only stdio MCP server."""
import asyncio
import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import jsonschema
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.types import ElicitResult

ALLOWED = {'get_me', 'get_file_contents', 'search_repositories'}
ROOT = Path(__file__).resolve().parents[3]


class GitHubMCP:
    def __init__(self, vault, connection=None):
        self.vault, self.connection = vault, connection
        self.users = {}

    def default_connection(self, elicitation):
        binary = Path(os.environ.get('GITHUB_MCP_BINARY', ROOT / '.local-models/github-mcp/github-mcp-server'))
        if not binary.is_file():
            raise ValueError('Install the official GitHub MCP binary with python -m scripts.install_github_mcp')
        return {'transport': 'stdio', 'command': str(binary),
                'args': ['stdio', '--read-only', '--toolsets=repos,context', '--oauth-scopes=read:user', '--content-window-size=20000'],
                'env': {'BROWSER': '/bin/false'}, 'session_kwargs': {'elicitation_callback': elicitation}}

    async def connect(self, user):
        old = self.users.get(user)
        if old and not old['task'].done():
            return self.status(user)
        state = {'status': 'connecting', 'authorization_url': None, 'authorization_message': None, 'login': None, 'queue': asyncio.Queue(),
                 'ready': asyncio.get_running_loop().create_future()}
        self.users[user] = state

        async def elicit(context, params):
            if getattr(params, 'mode', None) != 'url':
                return ElicitResult(action='decline')
            url = urlparse(params.url)
            if not (url.scheme == 'https' and url.hostname == 'github.com') and not (url.scheme == 'http' and url.hostname in {'localhost', '127.0.0.1'}):
                return ElicitResult(action='decline')
            state['authorization_url'], state['status'] = params.url, 'awaiting_authorization'
            state['authorization_message'] = params.message
            if not state['ready'].done():
                state['ready'].set_result(None)
            return ElicitResult(action='accept')

        async def run():
            try:
                connection = dict(self.connection or self.default_connection(elicit))
                if self.connection:
                    connection['session_kwargs'] = {'elicitation_callback': elicit}
                client = MultiServerMCPClient({'github': connection}, handle_tool_errors=False)
                # The task owns this context for its entire lifetime; no cancel scope crosses request tasks.
                async with client.session('github') as session:
                    catalog = (await session.list_tools()).tools
                    state['catalog'] = {t.name: t for t in catalog}
                    for name in ALLOWED:
                        tool = state['catalog'].get(name)
                        if not tool or not tool.annotations or tool.annotations.readOnlyHint is not True:
                            raise ValueError('Required GitHub read-only tool is missing')
                    identity = await asyncio.wait_for(session.call_tool('get_me', {}), 600)
                    data = self.decode(identity)
                    if not isinstance(data, dict) or not isinstance(data.get('login'), str):
                        # A provider auth URL in a tool response is not repository evidence.
                        raise ValueError('Complete GitHub OAuth and reconnect if the host does not support URL elicitation')
                    state['login'], state['status'], state['authorization_url'], state['authorization_message'] = data['login'], 'connected', None, None
                    self.vault.put(user, 'github:catalog', [t.model_dump(mode='json', exclude_none=True) for t in catalog])
                    if not state['ready'].done():
                        state['ready'].set_result(None)
                    while True:
                        name, arguments, future = await state['queue'].get()
                        if future.cancelled():
                            continue
                        try:
                            result = await asyncio.wait_for(session.call_tool(name, arguments), 30)
                            if not future.done():
                                future.set_result(result)
                        except Exception:
                            if not future.done():
                                future.set_exception(ValueError('GitHub read failed; reconnect or verify repository access'))
            except asyncio.CancelledError:
                state['status'] = 'disconnected'
                raise
            except Exception:
                state['status'] = 'failed'
                if not state['ready'].done():
                    state['ready'].set_result(None)
            finally:
                while not state['queue'].empty():
                    _, _, future = state['queue'].get_nowait()
                    if not future.done():
                        future.set_exception(ValueError('GitHub session closed; reconnect'))

        state['task'] = asyncio.create_task(run())
        try:
            await asyncio.wait_for(asyncio.shield(state['ready']), 20)
        except TimeoutError:
            pass
        return self.status(user)

    def status(self, user):
        state = self.users.get(user, {})
        return {'connected': state.get('status') == 'connected', 'status': state.get('status', 'disconnected'),
                'authorization_url': state.get('authorization_url'), 'login': state.get('login'),
                'authorization_message': state.get('authorization_message'),
                'read_only': True}

    async def call(self, user, name, arguments):
        if name not in ALLOWED:
            raise PermissionError('GitHub tool is outside the read-only allowlist')
        state = self.users.get(user)
        if not state or state['status'] != 'connected':
            raise ValueError('Connect GitHub from Settings first')
        tool = state['catalog'][name]
        jsonschema.validate(arguments, tool.inputSchema)
        future = asyncio.get_running_loop().create_future()
        await state['queue'].put((name, arguments, future))
        return await asyncio.wait_for(future, 35)

    @staticmethod
    def decode(result):
        if result.isError:
            raise ValueError('GitHub MCP rejected the read request')
        if result.structuredContent is not None:
            return result.structuredContent
        texts = [c.text for c in result.content if getattr(c, 'type', None) == 'text']
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except json.JSONDecodeError:
                pass
        raise ValueError('GitHub did not return a structured response')

    async def import_readme(self, user, freelancer, owner, repo, path='README.md', ref=None, authorship_confirmed=False):
        return await self.import_file(user, freelancer, owner, repo, path, ref, authorship_confirmed)

    async def import_file(self, user, freelancer, owner, repo, path='README.md', ref=None,
                          authorship_confirmed=False, kind='readme', persist=True):
        from rag.ingest.loaders import CODE_SUFFIXES
        state = self.users.get(user, {})
        if not authorship_confirmed or owner.lower() != str(state.get('login', '')).lower():
            raise ValueError('Confirm authorship and import from your own GitHub account; collaborator attribution is not implemented')
        if not all(re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', x) and x not in {'.', '..'} for x in [owner, repo]):
            raise ValueError('Invalid repository owner or name')
        parsed = PurePosixPath(path)
        valid_name = (parsed.name.lower() in {'readme', 'readme.md', 'readme.rst', 'readme.txt'} if kind == 'readme'
                      else kind == 'code' and parsed.suffix.lower() in CODE_SUFFIXES)
        if parsed.is_absolute() or '..' in parsed.parts or '\\' in path or not valid_name:
            raise ValueError('Select a repository README using a relative path')
        args = {'owner': owner, 'repo': repo, 'path': path}
        if ref:
            args['ref'] = ref
        result = await self.call(user, 'get_file_contents', args)
        text = None
        for content in result.content:
            resource = getattr(content, 'resource', None)
            if resource is not None and getattr(resource, 'text', None) is not None:
                text = resource.text
                break
        if text is None:
            value = self.decode(result)
            if isinstance(value, dict) and value.get('encoding') == 'base64' and isinstance(value.get('content'), str):
                text = base64.b64decode(value['content'], validate=False).decode('utf-8')
            elif isinstance(value, dict) and isinstance(value.get('content'), str):
                text = value['content']
        if not text or len(text.encode()) > 256_000:
            raise ValueError('README must be UTF-8 text and at most 256 KB; binary/resource-link-only responses are not imported')
        digest = hashlib.sha256(text.encode()).hexdigest()
        eid = 'github-' + hashlib.sha256(f'{user}|{owner}/{repo}|{path}|{ref}'.encode()).hexdigest()[:24]
        item = {'evidence_id': eid, 'type': kind, 'title': f'{owner}/{repo} — {path}',
                'summary': text, 'skills': [], 'source': f'https://github.com/{owner}/{repo}/blob/{ref or "HEAD"}/{path}',
                'date': datetime.now(timezone.utc).date().isoformat(), 'outcome': None, 'freelancer_id': freelancer,
                'provenance': 'real-github-mcp', 'content_sha256': digest, 'authorship_confirmed_by_user': True,
                'limitations': 'Repository text is untrusted source material; ownership/authorship confirmation does not establish performance or client outcomes.'}
        if persist:
            self.vault.put(user, 'github:evidence:' + eid, item)
        return item

    async def disconnect(self, user):
        state = self.users.pop(user, None)
        if state and not state['task'].done():
            state['task'].cancel()
            await asyncio.gather(state['task'], return_exceptions=True)

    async def close(self):
        for user in list(self.users):
            await self.disconnect(user)
