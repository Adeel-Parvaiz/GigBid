"""Only reachable after an approve. Idempotency key makes a replayed run submit/spend exactly once."""
from __future__ import annotations

from agent.deps import Deps
from agent.handoffs import ApprovalDecision, ProposalDraft
from agent.marketplace_context import approved_write
from agent.marketplace_port import MarketplaceError
from agent.nodes.approval import idempotency_key, preview_payload


def make(deps: Deps):
    async def submit(state):
        draft = ProposalDraft.model_validate(state["proposal_draft"])
        key = idempotency_key(state, draft)
        approval = state.get("approval")
        approval_token = approved_write.set(
            approval is not None and ApprovalDecision.model_validate(approval).action == "approve"
        )
        try:
            d = await deps.port.create_proposal_draft(preview_payload(state, draft), key)
            s = await deps.port.submit_proposal(d["draft_id"], key)
        except MarketplaceError as e:
            return {"status": "needs_attention", "errors": [str(e)]}
        finally:
            approved_write.reset(approval_token)
        return {"submission": s, "status": s.get('status', 'submitted')}
    return submit
