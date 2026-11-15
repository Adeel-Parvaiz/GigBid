"""Local OAuth + MCP fixture. Its tools are NOT claims about Upwork's real tool names."""
import base64
import hashlib
import secrets
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


def create_app():
    mcp = FastMCP('oauth-test-provider', stateless_http=True)
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
    draft = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
    access, codes, clients = set(), {}, {}
    counters = {'drafts': 0, 'refreshes': 0, 'official_previews': 0, 'official_executions': 0}

    destructive = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)

    @mcp.tool(name='upwork__manage_proposals', annotations=destructive,
              description='Returns a preview; call confirm_preview only after explicit user approval.')
    def official_proposal(action: str, org_uid: str, params: dict) -> dict:
        assert action == 'create'
        counters['official_previews'] += 1
        return {'preview_id': 'fixture-preview-1', 'preview': {'connects_cost': 8, 'connects_balance': 100,
                'cover_letter': params['cover_letter'], 'charged_amount': params['charged_amount']}}

    @mcp.tool(name='upwork__list_freelancer_proposals', annotations=read)
    def official_existing_proposals(action: str, org_uid: str, params: dict) -> dict:
        return {'data': {'invitations' if action == 'invitations' else 'proposals': []}, 'hasMore': False}

    @mcp.tool(name='upwork__confirm_preview', annotations=destructive)
    def official_confirm(action: str, org_uid: str, params: dict) -> dict:
        assert action == 'confirm' and params['type'] == 'proposal'
        counters['official_executions'] += 1
        return {'status': 'ok', 'note': 'Fixture execution only'}

    @mcp.tool(name='upwork__send_message', annotations=destructive)
    def official_send(action: str, org_uid: str, params: dict) -> dict:
        assert action == 'send'
        counters['official_executions'] += 1
        return {'status': 'ok', 'note': 'Fixture execution only'}

    @mcp.tool(annotations=read)
    def fixture_jobs(query: str | None = None, limit: int = 20) -> dict:
        return {'jobs': [{'job_id': 'job-001', 'client_id': 'client-001', 'title': 'Build a customer churn prediction baseline',
                          'description': 'Build a Python customer churn prediction baseline.', 'required_skills': ['Python'],
                          'connects_cost': 8, 'budget': {'min': 200, 'max': 500}}]}

    @mcp.tool(annotations=read)
    def fixture_job(job_id: str) -> dict:
        return fixture_jobs()['jobs'][0]

    @mcp.tool(annotations=read)
    def fixture_client(client_id: str) -> dict:
        return {'client_id': client_id, 'payment_verified': True, 'average_rating': 5, 'completed_projects': 10}

    @mcp.tool(annotations=read)
    def fixture_balance() -> dict:
        return {'balance': 100}

    @mcp.tool(annotations=read)
    def fixture_threads() -> dict:
        return {'threads': [{'thread_id': 'thread-001', 'job_id': 'job-001', 'client_id': 'client-001'}]}

    @mcp.tool(annotations=read)
    def fixture_messages(thread_id: str) -> dict:
        return {'thread_id': thread_id, 'messages': [{'id': 'm1', 'from': 'client', 'text': 'Can we schedule an interview?'}]}

    @mcp.tool(annotations=draft)
    def fixture_proposal_draft(proposal: dict) -> dict:
        counters['drafts'] += 1
        return {'confirmation_url': 'https://www.upwork.com/fixture/confirm-proposal'}

    @mcp.tool(annotations=draft)
    def fixture_message_draft(message: dict) -> dict:
        counters['drafts'] += 1
        return {'confirmation_url': 'https://www.upwork.com/fixture/confirm-message'}

    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)

    @app.middleware('http')
    async def auth(request, next_handler):
        if request.url.path.startswith('/mcp') and request.headers.get('authorization', '').removeprefix('Bearer ') not in access:
            base = str(request.base_url).rstrip('/')
            return JSONResponse({'error': 'unauthorized'}, status_code=401,
                                headers={'WWW-Authenticate': f'Bearer resource_metadata="{base}/.well-known/oauth-protected-resource/mcp"'})
        return await next_handler(request)

    @app.get('/.well-known/oauth-protected-resource/mcp')
    def resource(request: Request):
        base = str(request.base_url).rstrip('/')
        return {'resource': base + '/mcp', 'authorization_servers': [base], 'bearer_methods_supported': ['header']}

    @app.get('/.well-known/oauth-authorization-server')
    def metadata(request: Request):
        base = str(request.base_url).rstrip('/')
        return {'issuer': base, 'authorization_endpoint': base + '/authorize', 'token_endpoint': base + '/token',
                'registration_endpoint': base + '/register', 'response_types_supported': ['code'],
                'grant_types_supported': ['authorization_code', 'refresh_token'], 'token_endpoint_auth_methods_supported': ['none'],
                'code_challenge_methods_supported': ['S256']}

    @app.post('/register')
    async def register(request: Request):
        info = await request.json()
        cid = secrets.token_hex(12)
        clients[cid] = info
        return JSONResponse({**info, 'client_id': cid}, status_code=201)

    @app.get('/authorize')
    def authorize(request: Request):
        query = dict(request.query_params)
        if query.get('client_id') not in clients or query.get('redirect_uri') not in clients[query['client_id']]['redirect_uris']:
            return JSONResponse({'error': 'invalid_client'}, status_code=400)
        code = secrets.token_urlsafe(20)
        codes[code] = query
        return RedirectResponse(query['redirect_uri'] + '?' + urlencode({'code': code, 'state': query['state']}), status_code=302)

    @app.post('/token')
    async def token(request: Request):
        body = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
        if body.get('grant_type') == 'refresh_token':
            if body.get('refresh_token') != 'fixture-refresh':
                return JSONResponse({'error': 'invalid_grant'}, status_code=400)
            counters['refreshes'] += 1
        else:
            original = codes.pop(body.get('code'), None)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(body.get('code_verifier', '').encode()).digest()).rstrip(b'=').decode()
            if not original or challenge != original['code_challenge'] or body.get('redirect_uri') != original['redirect_uri'] or body.get('client_id') != original['client_id']:
                return JSONResponse({'error': 'invalid_grant'}, status_code=400)
        secret = secrets.token_urlsafe(24)
        access.add(secret)
        return {'access_token': secret, 'token_type': 'Bearer', 'refresh_token': 'fixture-refresh', 'expires_in': 3600}

    @app.get('/counters')
    def inspect_counters():
        return counters

    @app.post('/expire')
    def expire():
        access.clear()
        return {'expired': True}

    app.mount('/', mcp_app)
    return app
