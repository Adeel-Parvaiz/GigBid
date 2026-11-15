from types import SimpleNamespace
from unittest.mock import AsyncMock

from agent.nodes.approval import make


async def test_empty_grounded_proposal_stops_before_marketplace_preview():
    port = SimpleNamespace(create_proposal_draft=AsyncMock())
    result = await make(SimpleNamespace(port=port))({'proposal_draft': {'job_id': 'empty-job', 'claims': [], 'questions': []}})
    assert result['status'] == 'needs_attention'
    port.create_proposal_draft.assert_not_awaited()
