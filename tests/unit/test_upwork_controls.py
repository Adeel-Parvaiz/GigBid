import pytest

from agent.marketplace_context import marketplace_user
from agent.marketplace_port import MarketplaceError
from apps.api.auth.oauth_store import OAuthVault
from apps.api.auth.upwork_oauth import UpworkOAuth
from mcp_servers.marketplace.adapters.sample import SampleAdapter
from mcp_servers.marketplace.adapters.upwork_live import (
    RoutedMarketplacePort,
    marketplace_binding,
    validate_mapping,
)


def test_unsafe_or_unknown_tool_mapping_rejected():
    catalog = [{'name': 'submit_real_proposal', 'inputSchema': {},
                'annotations': {'readOnlyHint': False, 'destructiveHint': True}}]
    with pytest.raises(ValueError, match='non-destructive'):
        validate_mapping({'proposal_draft': {'tool': 'submit_real_proposal', 'effect': 'draft', 'confirmation_pointer': '/url'}}, catalog)
    with pytest.raises(ValueError, match='read-only'):
        validate_mapping({'get_job': {'tool': 'submit_real_proposal'}}, catalog)
    with pytest.raises(ValueError, match='discovery'):
        validate_mapping({'get_job': {'tool': 'invented-tool'}}, catalog)


async def test_changing_marketplace_cannot_retarget_a_pending_graph(tmp_path):
    service = UpworkOAuth(OAuthVault(tmp_path / 'oauth.sqlite'))
    port = RoutedMarketplacePort(SampleAdapter(), service)
    service.vault.put('alice', 'mode', 'upwork')
    service.vault.put('alice', 'binding', 'new-account-connection')
    u = marketplace_user.set('alice')
    b = marketplace_binding.set('simulator')
    try:
        with pytest.raises(MarketplaceError, match='marketplace_changed'):
            await port.get_connects_balance()
    finally:
        marketplace_user.reset(u)
        marketplace_binding.reset(b)
