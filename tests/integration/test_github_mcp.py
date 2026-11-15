import sys

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from apps.api.auth.github_mcp import GitHubMCP
from apps.api.auth.oauth_store import OAuthVault
from apps.api.auth.upwork_oauth import UpworkOAuth
from apps.api.main import create_app


def fixture_connection():
    return {'transport': 'stdio', 'command': sys.executable, 'args': ['-m', 'tests.fixtures.github_mcp_server']}


async def test_github_mcp_import_is_read_only_attributed_and_account_scoped(tmp_path):
    vault = OAuthVault(tmp_path / 'github.sqlite')
    service = GitHubMCP(vault, fixture_connection())
    try:
        assert (await service.connect('alice'))['connected']
        assert not service.status('bob')['connected']
        with pytest.raises(PermissionError):
            await service.call('alice', 'create_issue', {})
        with pytest.raises(ValueError, match='Connect GitHub'):
            await service.call('bob', 'get_me', {})
        with pytest.raises(ValueError, match='Confirm authorship'):
            await service.import_readme('alice', 'profile-a', 'someone-else', 'project', authorship_confirmed=True)
        with pytest.raises(ValueError, match='relative path'):
            await service.import_readme('alice', 'profile-a', 'fixture-owner', 'project', path='../README.md', authorship_confirmed=True)
        item = await service.import_readme('alice', 'profile-a', 'fixture-owner', 'project', authorship_confirmed=True)
        assert item['type'] == 'readme' and item['outcome'] is None
        assert item['source'] == 'https://github.com/fixture-owner/project/blob/HEAD/README.md'
        assert len(item['content_sha256']) == 64 and item['provenance'] == 'real-github-mcp'
        assert vault.list_prefix('bob', 'github:evidence:') == []
        assert len(vault.list_prefix('alice', 'github:evidence:')) == 1
        await service.import_readme('alice', 'profile-a', 'fixture-owner', 'project', authorship_confirmed=True)
        assert len(vault.list_prefix('alice', 'github:evidence:')) == 1
        await service.disconnect('alice')
        assert not service.status('alice')['connected']
        assert len(OAuthVault(tmp_path / 'github.sqlite').list_prefix('alice', 'github:evidence:')) == 1
    finally:
        await service.close()


async def test_github_application_routes_reject_other_user_import_access(tmp_path, make_deps):
    vault = OAuthVault(tmp_path / 'routes.sqlite')
    service = GitHubMCP(vault, fixture_connection())
    app = create_app(deps=make_deps(), checkpointer=InMemorySaver(), upwork=UpworkOAuth(vault), github_service=service)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://app') as client:
            assert (await client.get('/connections/github')).status_code == 401
            users = []
            for email in ['github-alice@example.com', 'github-bob@example.com']:
                result = (await client.post('/auth/register', json={'email': email, 'password': 'fixture-password', 'freelancer_id': 'sample-ai-engineer'})).json()
                users.append({'Authorization': 'Bearer ' + result['token']})
            assert (await client.post('/connections/github/authorize', headers=users[0])).json()['connected']
            imported = await client.post('/connections/github/imports', headers=users[0], json={'owner': 'fixture-owner', 'repo': 'project', 'authorship_confirmed': True})
            assert imported.status_code == 200
            assert len((await client.get('/connections/github/imports', headers=users[0])).json()['items']) == 1
            assert (await client.get('/connections/github/imports', headers=users[1])).json()['items'] == []
    finally:
        await service.close()


async def test_imported_readme_is_retrievable_through_tenant_bound_portfolio_mcp(tmp_path, monkeypatch):
    from agent.config import load_config
    from agent.mcp_client import AgentTools, portfolio_connection
    vault = OAuthVault(tmp_path / 'portfolio.sqlite')
    monkeypatch.setenv('OAUTH_DB', str(vault.database))
    service = GitHubMCP(vault, fixture_connection())
    try:
        await service.connect('alice')
        item = await service.import_readme('alice', 'sample-ai-engineer', 'fixture-owner', 'project', authorship_confirmed=True)
        cfg = load_config(overrides={'portfolio': {'transport': 'stdio'}})
        alice = AgentTools({'portfolio': portfolio_connection(cfg, 'alice', 'sample-ai-engineer')})
        found = await alice.call('fit_matcher', 'search_evidence', {'requirement': 'reproducible scripts', 'k': 10})
        assert any(row['evidence_id'] == item['evidence_id'] for row in found['items'])
        bob = AgentTools({'portfolio': portfolio_connection(cfg, 'bob', 'sample-ai-engineer')})
        other = await bob.call('fit_matcher', 'search_evidence', {'requirement': 'reproducible scripts', 'k': 10})
        assert all(row['evidence_id'] != item['evidence_id'] for row in other['items'])
    finally:
        await service.close()
