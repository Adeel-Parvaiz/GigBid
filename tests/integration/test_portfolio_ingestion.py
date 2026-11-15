import base64

import httpx
from langgraph.checkpoint.memory import InMemorySaver

from apps.api.auth.github_mcp import GitHubMCP
from apps.api.auth.oauth_store import OAuthVault
from apps.api.auth.upwork_oauth import UpworkOAuth
from apps.api.main import create_app
from tests.integration.test_github_mcp import fixture_connection
from tests.unit.test_portfolio_ingestion import META


async def test_ui_ingestion_api_auth_ownership_search_and_github_mcp(tmp_path, make_deps):
    vault = OAuthVault(tmp_path / 'api.sqlite')
    github = GitHubMCP(vault, fixture_connection())
    app = create_app(deps=make_deps(), checkpointer=InMemorySaver(), upwork=UpworkOAuth(vault), github_service=github)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://app') as client:
            assert (await client.get('/portfolio/documents')).status_code == 401
            headers = []
            for name in ['b1alice', 'b1bob']:
                account = (await client.post('/auth/register', json={'email': name + '@example.test', 'password': 'fixture-password', 'freelancer_id': 'sample-ai-engineer'})).json()
                headers.append({'Authorization': 'Bearer ' + account['token']})
            body = {'filename': 'case.md', 'kind': 'case_study', 'content_base64': base64.b64encode(b'uniqueb1api Python project').decode(), 'metadata': META}
            created = await client.post('/portfolio/documents', headers=headers[0], json=body)
            assert created.status_code == 200, created.text
            doc = created.json()
            assert (await client.post('/portfolio/documents', headers=headers[0], json=body)).json()['embedded_chunks'] == 0
            found = (await client.get('/portfolio/search?query=uniqueb1api', headers=headers[0])).json()['items']
            assert any(i['document_id'] == doc['document_id'] for i in found)
            assert (await client.get('/portfolio/documents', headers=headers[1])).json()['items'] == []
            assert (await client.delete('/portfolio/documents/' + doc['document_id'], headers=headers[1])).status_code == 404
            assert (await client.post('/portfolio/documents', headers=headers[0], json={**body, 'kind': 'code'})).status_code == 422
            assert (await client.post('/portfolio/documents', headers=headers[0], json={**body, 'metadata': {**META, 'authorship_confirmed': False}})).status_code == 422
            assert (await client.post('/portfolio/documents', headers=headers[0], json={**body, 'kind': 'past_proposal'})).status_code == 422
            # Connect the fixture as the authenticated application's actual owner ID.
            # Authentication store lookup is deliberately avoided; capture the registered user via /auth/me.
            me = (await client.get('/auth/me', headers=headers[0])).json()
            await github.connect(me['user_id'])
            for kind, path in [('readme', 'README.md'), ('code', 'src/main.py')]:
                imported = await client.post('/portfolio/github', headers=headers[0], json={
                    'owner': 'fixture-owner', 'repo': 'project', 'path': path, 'kind': kind, 'metadata': META})
                assert imported.status_code == 200, imported.text
                saved = next(d for d in vault.list_prefix(me['user_id'], 'portfolio:document:') if d['type'] == kind)
                assert saved['chunks'][0]['provenance'] == 'synthetic'
                assert saved['chunks'][0]['ingestion_method'] == 'github-mcp'
                assert saved['chunks'][0]['source'].startswith('https://github.com/')
            assert (await client.delete('/portfolio/documents/' + doc['document_id'], headers=headers[0])).status_code == 200
    finally:
        await github.close()
