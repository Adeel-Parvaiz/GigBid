import pytest

from agent.marketplace_port import MarketplaceError
from apps.api.auth.oauth_store import OAuthVault
from mcp_servers.marketplace.adapters.upwork_live import validate_mapping
from mcp_servers.marketplace.adapters.upwork_normalize import normalize, official_read_mapping


def test_real_response_shape_preserves_unknown_cost_and_client_sample(tmp_path):
    vault = OAuthVault(tmp_path / 'normalizer.sqlite')
    jobs = normalize('official_job_search', {'jobs': [{'id': '123', 'title': 'Python job', 'budget': '50.00',
                     'skills': ['Python'], 'client': {'verification_status': 'VERIFIED'}}]}, vault, 'alice', {})
    assert jobs[0]['connects_cost'] is None
    detail = {'data': {'marketplaceJobPosting': {'id': '123', 'content': {'title': 'Python job'},
              'clientCompanyPublic': {'id': 'client-1'}, 'contractTerms': {'fixedPriceContractTerms': {'amount': {'rawValue': '50', 'currency': 'USD'}}}}},
              'connects_cost': 11, 'can_apply': False, 'client_record': {'contracts_total': 12, 'contracts_active': 6, 'feedback_score': 5}}
    job = normalize('official_job_detail', detail, vault, 'alice', {})
    assert job['connects_cost'] == 11 and job['required_skills'] == ['Python']
    client = vault.get('alice', 'client:client-1')
    assert client['payment_verified'] is True
    assert 'completed_projects' not in client
    assert normalize('official_balance', {'balance': {'connectsBalance': 0}}, vault, 'alice', {}) == {'balance': 0, 'provenance': 'upwork-live'}


def test_rooms_and_messages_fail_closed_for_unknown_author_side(tmp_path):
    vault = OAuthVault(tmp_path / 'messages.sqlite')
    assert normalize('official_rooms', {'data': {'rooms': []}}, vault, 'alice', {}) == []
    message = {'id': 'message-1', 'text': 'Interview?', 'from_side': 'client'}
    out = normalize('official_messages', {'data': {'messages': [message]}}, vault, 'alice', {'thread_id': 'room-1'})
    assert out['messages'][0]['from'] == 'client'
    with pytest.raises(MarketplaceError, match='authoritative sender'):
        normalize('official_messages', {'data': {'messages': [{'id': 'm1', 'text': 'Unknown sender'}]}}, vault, 'alice', {'thread_id': 'room-1'})


def test_official_mapping_exposes_no_write_tool():
    mapping = official_read_mapping()
    assert not {'proposal_draft', 'message_draft'} & mapping.keys()
    catalog = [{'name': name, 'annotations': {'readOnlyHint': True}} for name in ['upwork__find_jobs', 'upwork__get_profile', 'upwork__get_messages']]
    validate_mapping(mapping, catalog)
