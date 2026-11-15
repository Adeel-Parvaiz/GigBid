import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from apps.gigsim.main import Simulator, create_app
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data/sample'


def setup(tmp_path, connects=100):
    app = create_app(DATA, tmp_path / 'sim.sqlite', {'alice-token': 'alice', 'bob-token': 'bob'}, connects)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://sim')
    port = GigSimAdapter('http://sim', ROOT / 'config/gigsim_contract.json', client, 'alice-token')
    return app, client, port


async def test_auth_validation_and_gold_isolation(tmp_path):
    app, client, port = setup(tmp_path)
    async with client:
        assert (await client.get('/v1/jobs')).status_code == 401
        assert (await client.get('/health')).json()['synthetic']
        jobs = await port.search_jobs()
        assert jobs and all('label' not in j for j in jobs)
        assert (await client.get('/v1/jobs?limit=-1', headers={'Authorization': 'Bearer alice-token'})).status_code == 422
        bad = await client.post('/v1/drafts', json={'proposal': {}, 'key': 'invalid-proposal'},
                                headers={'Authorization': 'Bearer alice-token', 'Idempotency-Key': 'invalid-proposal'})
        assert bad.status_code == 422


async def test_preview_persistence_account_isolation_and_outcomes(tmp_path):
    app, client, port = setup(tmp_path)
    async with client:
        job = (await port.search_jobs())[0]
        payload = {'job_id': job['job_id'], 'cover_letter': 'Python churn analysis with a reproducible baseline.', 'bid_amount': 100}
        assert (await port.create_proposal_draft(payload, 'proposal-key', True))['dry_run']
        assert (await port.get_connects_balance())['balance'] == 100
        draft = await port.create_proposal_draft(payload, 'proposal-key')
        await port.submit_proposal(draft['draft_id'], 'submit-key')
        await port.submit_proposal(draft['draft_id'], 'another-submit-key')
        assert (await port.get_connects_balance())['balance'] == 100 - job['connects_cost']
        threads = await port.list_threads()
        await port.send_message(threads[0]['thread_id'], 'A persistent response.', 'message-key')
        result = (await client.get('/v1/outcomes', headers={'Authorization': 'Bearer alice-token'})).json()
        assert len(result['outcomes']) == 1 and 'p_reply' not in result['outcomes'][0]
        bob = GigSimAdapter('http://sim', ROOT / 'config/gigsim_contract.json', client, 'bob-token')
        assert (await bob.get_connects_balance())['balance'] == 100
        assert 'A persistent response.' not in str(await bob.list_messages(threads[0]['thread_id']))
    _, client2, port2 = setup(tmp_path)
    async with client2:
        assert (await port2.get_connects_balance())['balance'] == 100 - job['connects_cost']
        assert 'A persistent response.' in str(await port2.list_messages(threads[0]['thread_id']))
        assert (await port2.create_proposal_draft(payload, 'proposal-key'))['replayed']
        changed = {**payload, 'bid_amount': 200}
        with pytest.raises(Exception, match='HTTP 409'):
            await port2.create_proposal_draft(changed, 'proposal-key')


def test_concurrent_duplicate_submissions_spend_once(tmp_path):
    sim = Simulator(DATA, tmp_path / 'concurrent.sqlite')
    job = asyncio.run(sim.adapter().search_jobs())[0]
    draft = sim.call('alice', 'create_proposal_draft', {'payload': {'job_id': job['job_id']}, 'idempotency_key': 'draft-key'})
    def submit(i):
        return sim.call('alice', 'submit_proposal', {'draft_id': draft['draft_id'], 'idempotency_key': f'submit-{i}'})
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(submit, range(16)))
    assert sum(not r['replayed'] for r in results) == 1
    assert sim.call('alice', 'get_connects_balance', {})['balance'] == 100 - job['connects_cost']


async def test_insufficient_connects_has_no_side_effects(tmp_path):
    _, client, port = setup(tmp_path, connects=0)
    async with client:
        job = (await port.search_jobs())[0]
        draft = await port.create_proposal_draft({'job_id': job['job_id'], 'cover_letter': 'A valid proposal.', 'bid_amount': 100}, 'proposal-key')
        with pytest.raises(Exception, match='HTTP 409'):
            await port.submit_proposal(draft['draft_id'], 'submit-key')
        assert (await port.get_connects_balance())['balance'] == 0
