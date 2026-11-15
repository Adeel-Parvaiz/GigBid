from unittest.mock import AsyncMock

import pytest

from agent.marketplace_context import approved_write
from agent.marketplace_port import MarketplaceError
from apps.api.auth.oauth_store import OAuthVault
from apps.api.auth.upwork_oauth import UpworkOAuth
from mcp_servers.marketplace.adapters.upwork_live import UpworkLiveAdapter


async def test_uncertain_provider_write_is_not_repeated_after_restart(tmp_path):
    vault = OAuthVault(tmp_path / 'writes.sqlite')
    service = UpworkOAuth(vault)
    first = UpworkLiveAdapter(service, 'alice')
    first._call = AsyncMock(side_effect=MarketplaceError('marketplace_unavailable'))
    approval = approved_write.set(True)
    try:
        with pytest.raises(MarketplaceError, match='marketplace_unavailable'):
            await first.send_message('thread-1', 'Approved text.', 'uncertain-key')
        restored = UpworkLiveAdapter(UpworkOAuth(OAuthVault(tmp_path / 'writes.sqlite')), 'alice')
        restored._call = AsyncMock()
        with pytest.raises(MarketplaceError, match='upwork_write_uncertain'):
            await restored.send_message('thread-1', 'Approved text.', 'uncertain-key')
        restored._call.assert_not_awaited()
        with pytest.raises(MarketplaceError, match='idempotency_conflict'):
            await restored.send_message('thread-1', 'Changed text.', 'uncertain-key')
        assert first._call.await_count == 1
    finally:
        approved_write.reset(approval)
