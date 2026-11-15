import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from agent.marketplace_context import approved_write, marketplace_user
from agent.marketplace_port import MarketplaceError
from apps.api.auth.oauth_store import OAuthVault
from apps.api.auth.upwork_oauth import UpworkOAuth
from apps.api.main import create_app
from mcp_servers.marketplace.adapters.sample import SampleAdapter
from mcp_servers.marketplace.adapters.upwork_live import (
    RoutedMarketplacePort,
    UpworkLiveAdapter,
    validate_mapping,
)
from tests.conftest import free_port


@pytest.fixture
def oauth_server(tmp_path):
    port = free_port()
    root = Path(__file__).resolve().parents[2]
    with (tmp_path / 'oauth.log').open('w') as log:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tests.fixtures.upwork_oauth_app:create_app', '--factory', '--port', str(port)], cwd=root, env=os.environ.copy(), stdout=log, stderr=log)
    base = f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try:
                if httpx.get(base + '/counters').status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        yield base
    finally:
        process.terminate()
        process.wait(10)


def fixture_mapping():
    return {
        'search_jobs': {'tool': 'fixture_jobs', 'arguments': {'query': '$query', 'limit': '$limit'}, 'response_pointer': '/jobs'},
        'get_job': {'tool': 'fixture_job', 'arguments': {'job_id': '$job_id'}},
        'get_client_history': {'tool': 'fixture_client', 'arguments': {'client_id': '$client_id'}},
        'get_connects_balance': {'tool': 'fixture_balance'},
        'list_threads': {'tool': 'fixture_threads', 'response_pointer': '/threads'},
        'list_messages': {'tool': 'fixture_messages', 'arguments': {'thread_id': '$thread_id'}},
        'proposal_draft': {'tool': 'fixture_proposal_draft', 'arguments': {'proposal': '$payload'}, 'effect': 'draft', 'confirmation_pointer': '/confirmation_url'},
        'message_draft': {'tool': 'fixture_message_draft', 'arguments': {'message': '$payload'}, 'effect': 'draft', 'confirmation_pointer': '/confirmation_url'},
    }


async def authorize(service, base, user):
    start = await service.start(user)
    assert start['status'] == 'awaiting_authorization'
    query = parse_qs(urlparse(start['authorization_url']).query)
    assert query['code_challenge_method'] == ['S256']
    async with httpx.AsyncClient() as client:
        response = await client.get(start['authorization_url'], follow_redirects=False)
    callback = parse_qs(urlparse(response.headers['location']).query)
    with pytest.raises(ValueError, match='state'):
        await service.finish('wrong-state', callback['code'][0])
    assert await service.finish(callback['state'][0], callback['code'][0])
    with pytest.raises(ValueError):
        await service.finish(callback['state'][0], callback['code'][0])


async def test_actual_sdk_oauth_pkce_discovery_refresh_and_draft_only_port(oauth_server, tmp_path):
    service = UpworkOAuth(OAuthVault(tmp_path / 'tokens.sqlite'), oauth_server + '/mcp', 'http://127.0.0.1:8000/connections/upwork/callback')
    try:
        await authorize(service, oauth_server, 'alice')
        assert service.vault.get('bob', 'tokens') is None
        catalog = service.vault.get('alice', 'catalog')
        mapping = fixture_mapping()
        validate_mapping(mapping, catalog)
        service.vault.put('alice', 'mapping', mapping)
        port = UpworkLiveAdapter(service, 'alice')
        jobs = await port.search_jobs('python')
        job = await port.get_job(jobs[0]['job_id'])
        assert (await port.get_connects_balance())['balance'] == 100
        assert (await port.get_client_history(job['client_id']))['payment_verified']
        thread = (await port.list_threads())[0]['thread_id']
        assert (await port.list_messages(thread))['messages']
        payload = {'job_id': job['job_id'], 'cover_letter': 'Grounded local fixture proposal.', 'bid_amount': 200}
        preview = await port.create_proposal_draft(payload, 'fixture-key', True)
        assert preview['dry_run'] and preview['requires_platform_confirmation']
        with pytest.raises(MarketplaceError, match='approval_required'):
            await port.create_proposal_draft(payload, 'fixture-key')
        token = approved_write.set(True)
        try:
            draft = await port.create_proposal_draft(payload, 'fixture-key')
            outcome = await port.submit_proposal(draft['draft_id'], 'fixture-key')
            assert outcome['status'] == 'awaiting_platform_confirmation' and outcome['connects_spent'] == 0
            assert (await port.submit_proposal(draft['draft_id'], 'fixture-key'))['replayed']
            message = await port.send_message(thread, 'Approved draft reply.', 'message-key')
            assert message['status'] == 'awaiting_platform_confirmation'
        finally:
            approved_write.reset(token)
        async with httpx.AsyncClient() as client:
            assert (await client.get(oauth_server + '/counters')).json()['drafts'] == 2
        record = service.vault.get('alice', 'tokens')
        record['expires_at'] = 0
        service.vault.put('alice', 'tokens', record)
        async with httpx.AsyncClient() as client:
            await client.post(oauth_server + '/expire')
        await service.discover('alice')
        async with httpx.AsyncClient() as client:
            assert (await client.get(oauth_server + '/counters')).json()['refreshes'] >= 1
        # Per-user routing cannot borrow the connected account for another application user.
        service.vault.put('alice', 'mode', 'upwork')
        proxy = RoutedMarketplacePort(SampleAdapter(), service)
        user_token = marketplace_user.set('bob')
        try:
            assert (await proxy.get_connects_balance())['balance'] == 100
        finally:
            marketplace_user.reset(user_token)
        service.disconnect('alice')
        assert service.vault.get('alice', 'tokens') is None
    finally:
        await service.close()


async def test_application_oauth_callback_user_scoping_and_provider_switch(oauth_server, tmp_path, make_deps):
    from langgraph.checkpoint.memory import InMemorySaver
    service = UpworkOAuth(OAuthVault(tmp_path / 'api-oauth.sqlite'), oauth_server + '/mcp', 'http://127.0.0.1:8000/connections/upwork/callback')
    app = create_app(deps=make_deps(), checkpointer=InMemorySaver(), upwork=service)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://application') as client:
            assert (await client.get('/connections/upwork')).status_code == 401
            registration = await client.post('/auth/register', json={'email': 'oauth-alice@example.com', 'password': 'oauth-test-password', 'freelancer_id': 'sample-ai-engineer'})
            headers = {'Authorization': 'Bearer ' + registration.json()['token']}
            other = await client.post('/auth/register', json={'email': 'oauth-bob@example.com', 'password': 'oauth-test-password', 'freelancer_id': 'sample-ai-engineer'})
            bob = {'Authorization': 'Bearer ' + other.json()['token']}
            start = (await client.post('/connections/upwork/authorize', headers=headers)).json()
            async with httpx.AsyncClient() as provider:
                consent = await provider.get(start['authorization_url'], follow_redirects=False)
            redirect = urlparse(consent.headers['location'])
            assert (await client.get('/connections/upwork/callback?state=bad&code=bad')).status_code == 400
            complete = await client.get(redirect.path + '?' + redirect.query, follow_redirects=False)
            assert complete.status_code == 303 and complete.headers['location'] == '/upwork-connected'
            assert (await client.get('/connections/upwork', headers=headers)).json()['connected']
            assert not (await client.get('/connections/upwork', headers=bob)).json()['connected']
            catalog = (await client.get('/connections/upwork/catalog', headers=headers)).json()
            mapped = await client.put('/connections/upwork/mapping', headers=headers,
                                      json={'catalog_sha256': catalog['sha256'], 'operations': fixture_mapping()})
            assert mapped.status_code == 200
            activate = await client.put('/connections/upwork/mode', headers=headers, json={'mode': 'upwork'})
            assert activate.status_code == 200
            assert len((await client.get('/jobs', headers=headers)).json()) == 1
            assert len((await client.get('/jobs', headers=bob)).json()) == 5
            assert (await client.delete('/connections/upwork', headers=headers)).status_code == 200
            assert not (await client.get('/connections/upwork', headers=headers)).json()['connected']
    finally:
        await service.close()


async def test_official_action_contract_requires_two_human_gates_and_never_repeats(oauth_server, tmp_path, make_deps):
    from langgraph.checkpoint.memory import InMemorySaver

    from apps.api.auth.users import UserStore
    users = UserStore(secret='fixture-session-secret')
    user = users.create('two-gates@example.com', 'fixture-password', 'sample-ai-engineer')
    uid = user['user_id']
    service = UpworkOAuth(OAuthVault(tmp_path / 'two-gates.sqlite'), oauth_server + '/mcp', 'http://127.0.0.1:8000/connections/upwork/callback')
    await authorize(service, oauth_server, uid)
    mapping = fixture_mapping()
    mapping['proposal_draft'] = {'tool': 'upwork__manage_proposals', 'effect': 'official_proposal_preview'}
    mapping['message_draft'] = {'source': 'local_message_draft'}
    validate_mapping(mapping, service.vault.get(uid, 'catalog'))
    for key, value in [('mapping', mapping), ('mode', 'upwork'), ('binding', 'fixture-connection'), ('account', {'org_uid': 'fixture-org'})]:
        service.vault.put(uid, key, value)
    app = create_app(deps=make_deps(), checkpointer=InMemorySaver(), users=users, upwork=service, seed=False)
    headers = {'Authorization': 'Bearer ' + users.issue(uid)}
    async def counters():
        async with httpx.AsyncClient() as remote:
            return (await remote.get(oauth_server + '/counters')).json()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://application') as client:
            rid = (await client.post('/jobs/job-001/runs', headers=headers)).json()['run_id']
            async def settled():
                for _ in range(300):
                    result = (await client.get(f'/runs/{rid}', headers=headers)).json()
                    if result['status'] != 'running':
                        return result
                    await asyncio.sleep(.03)
                raise AssertionError('Graph did not settle')
            gate = await settled()
            assert gate['status'] == 'awaiting_approval'
            assert (await counters())['official_previews'] == 0
            await client.post(f'/runs/{rid}/approval', headers=headers, json={'action': 'approve'})
            platform = await settled()
            assert platform['status'] == 'awaiting_platform_confirmation'
            assert (await counters())['official_previews'] == 1
            assert (await counters())['official_executions'] == 0
            data = platform['summary']['submission']
            payload = {'review_hash': data['review_hash'], 'confirm_on_upwork': True, 'attachments_choice': 'none'}
            assert (await client.post(f'/runs/{rid}/platform-confirmation', json=payload)).status_code == 401
            wrong = {**payload, 'review_hash': '0' * 64}
            assert (await client.post(f'/runs/{rid}/platform-confirmation', headers=headers, json=wrong)).status_code == 409
            assert (await client.post(f'/runs/{rid}/platform-confirmation', headers=headers, json={**payload, 'confirm_on_upwork': False})).status_code == 409
            confirmed = await client.post(f'/runs/{rid}/platform-confirmation', headers=headers, json=payload)
            assert confirmed.status_code == 200
            assert confirmed.json()['status'] == 'platform_confirmation_recorded'
            assert (await client.post(f'/runs/{rid}/platform-confirmation', headers=headers, json=payload)).status_code == 409
            assert (await counters())['official_executions'] == 1
            # A message is staged locally; official Send Message is called only after the second approval.
            port = UpworkLiveAdapter(service, uid)
            approval = approved_write.set(True)
            try:
                draft = await port.send_message('thread-001', 'An approved fixture reply.', 'official-message')
                assert (await counters())['official_executions'] == 1
                await port.confirm_platform_action(draft['platform_action_id'], draft['review_hash'])
                assert (await counters())['official_executions'] == 2
            finally:
                approved_write.reset(approval)
    finally:
        await service.close()
