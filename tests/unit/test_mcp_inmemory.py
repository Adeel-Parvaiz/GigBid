"""Protocol-level unit tests using the official SDK in-memory client, not direct function calls."""
from pathlib import Path

from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.marketplace.adapters.sample import SampleAdapter
from mcp_servers.marketplace.server import build_server as marketplace_server
from mcp_servers.marketplace.tools import MarketplaceService
from mcp_servers.portfolio.server import build_server as portfolio_server
from mcp_servers.portfolio.tools import PortfolioStore
from mcp_servers.workspace.server import build_server as workspace_server
from mcp_servers.workspace.tools import WorkspaceService

DATA = Path(__file__).resolve().parents[2] / 'data/sample'


async def test_portfolio_tools_resources_and_prompts_over_inmemory_mcp():
    async with connect(portfolio_server(PortfolioStore(DATA, freelancer_id='sample-ai-engineer'))) as session:
        assert {t.name for t in (await session.list_tools()).tools} == {'search_evidence', 'get_case_study', 'list_skills'}
        result = await session.call_tool('search_evidence', {'requirement': 'Python churn prediction', 'k': 3})
        assert not result.isError
        evidence = result.structuredContent['items'][0]
        assert {'type', 'source', 'date', 'outcome'} <= evidence.keys()
        full = await session.call_tool('get_case_study', {'id': evidence['evidence_id']})
        assert full.structuredContent['evidence_id'] == evidence['evidence_id']
        assert (await session.call_tool('list_skills', {})).structuredContent['skills']
        templates = (await session.list_resource_templates()).resourceTemplates
        assert {t.uriTemplate for t in templates} == {'portfolio://case/{case_id}', 'portfolio://proposal/{proposal_id}'}
        resource = await session.read_resource('portfolio://case/' + evidence['evidence_id'])
        assert evidence['evidence_id'] in resource.contents[0].text
        proposals = await session.call_tool('search_evidence', {'requirement': 'Python', 'filters': {'type': 'past_proposal'}, 'k': 3})
        pid = proposals.structuredContent['items'][0]['evidence_id']
        assert pid in (await session.read_resource('portfolio://proposal/' + pid)).contents[0].text
        prompts = (await session.list_prompts()).prompts
        assert {p.name for p in prompts} == {'answer_screening_question', 'find_evidence_for_requirement', 'draft_proposal'}
        prompt = await session.get_prompt('answer_screening_question', arguments={'question': 'What Python work have you done?'})
        assert 'What Python work have you done?' in prompt.messages[0].content.text
        assert (await session.call_tool('search_evidence', {'requirement': 'x'})).isError
        assert (await session.call_tool('search_evidence', {'requirement': 'Python', 'filters': {'freelancer_id': 'other-user'}})).isError


async def test_all_marketplace_operations_and_idempotency_over_inmemory_mcp(tmp_path):
    adapter = SampleAdapter(DATA)
    async with connect(marketplace_server(MarketplaceService(adapter, tmp_path / 'audit.jsonl', per_minute=100))) as session:
        assert len((await session.list_tools()).tools) == 9
        jobs = (await session.call_tool('search_jobs', {'query': 'churn'})).structuredContent['jobs']
        job = (await session.call_tool('get_job', {'job_id': jobs[0]['job_id']})).structuredContent
        assert (await session.call_tool('get_client_history', {'client_id': job['client_id']})).structuredContent['client_id'] == job['client_id']
        assert (await session.call_tool('get_connects_balance', {})).structuredContent['balance'] == 100
        proposal = {'job_id': job['job_id'], 'cover_letter': 'An authorized in-memory fixture proposal.',
                    'bid_amount': 300, 'idempotency_key': 'memory-proposal', 'dry_run': True}
        preview = await session.call_tool('create_proposal_draft', {'proposal': proposal})
        assert preview.structuredContent['dry_run'] and not adapter.drafts
        proposal['dry_run'] = False
        draft = (await session.call_tool('create_proposal_draft', {'proposal': proposal})).structuredContent
        args = {'draft_id': draft['draft_id'], 'idempotency_key': 'memory-submit'}
        assert not (await session.call_tool('submit_proposal', args)).structuredContent['replayed']
        assert (await session.call_tool('submit_proposal', args)).structuredContent['replayed']
        assert adapter.balance == 100 - job['connects_cost']
        threads = (await session.call_tool('list_threads', {})).structuredContent['threads']
        tid = threads[0]['thread_id']
        assert (await session.call_tool('list_messages', {'thread_id': tid})).structuredContent['messages']
        message = {'thread_id': tid, 'text': 'Approved fixture reply.', 'idempotency_key': 'memory-message'}
        assert not (await session.call_tool('send_message', message)).structuredContent['replayed']
        assert (await session.call_tool('send_message', message)).structuredContent['replayed']
        assert len(adapter.sent) == 1
        assert (await session.call_tool('create_proposal_draft', {'proposal': {**proposal, 'bid_amount': -1}})).isError


async def test_workspace_slots_hold_and_unsent_email_over_inmemory_mcp():
    service = WorkspaceService()
    async with connect(workspace_server(service)) as session:
        assert len((await session.list_tools()).tools) == 3
        slots = (await session.call_tool('get_free_slots', {'start_date': '2026-11-16', 'days': 5, 'limit': 3})).structuredContent['slots']
        assert slots
        hold = {'start': slots[0]['start'], 'title': 'Fixture interview', 'idempotency_key': 'memory-hold'}
        assert (await session.call_tool('create_tentative_hold', hold)).structuredContent['status'] == 'tentative'
        assert (await session.call_tool('create_tentative_hold', hold)).structuredContent['replayed']
        draft = {'to': 'client@example.com', 'subject': 'Fixture interview', 'body': 'Please review.', 'idempotency_key': 'memory-email'}
        assert (await session.call_tool('create_email_draft', draft)).structuredContent['status'] == 'draft'
        assert (await session.call_tool('create_email_draft', draft)).structuredContent['replayed']
        assert len(service.holds) == 1 and len(service.emails) == 1
        assert (await session.call_tool('get_free_slots', {'start_date': '2026-13-40'})).isError
        assert (await session.call_tool('create_email_draft', {**draft, 'idempotency_key': 'x'})).isError
