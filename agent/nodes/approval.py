"""Human approval gate (R4/C5). Pauses the graph with interrupt(); the web UI resumes it.

The payload carries everything the reviewer needs: draft, evidence behind each claim, risk, price
rationale and the dry_run preview of exactly what would be sent and what it costs.
"""
from __future__ import annotations

import difflib
import hashlib

from langgraph.types import interrupt

from agent.deps import Deps
from agent.handoffs import (
    ApprovalDecision,
    ClaimVerdict,
    ComplianceVerdict,
    Critique,
    PriceQuote,
    ProposalDraft,
    RiskReport,
)


def preview_payload(state: dict, draft: ProposalDraft) -> dict:
    quote = PriceQuote.model_validate(state["price_quote"])
    return {"job_id": state["job_id"], "freelancer_id": state["profile"]["freelancer_id"],
            "cover_letter": draft.cover_letter, "screening_answers": draft.screening_answers,
            "bid_amount": quote.amount, "currency": quote.currency}


def idempotency_key(state: dict, draft: ProposalDraft) -> str:
    """Same freelancer + job + final text => same key, on any thread or after any restart."""
    raw = f"{state['profile']['freelancer_id']}|{state['job_id']}|{draft.cover_letter}|{draft.screening_answers}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def make(deps: Deps):
    async def approval(state):
        draft = ProposalDraft.model_validate(state["proposal_draft"])
        quote = PriceQuote.model_validate(state["price_quote"])
        risk = RiskReport.model_validate(state["risk_report"])
        compliance = ComplianceVerdict.model_validate(state["compliance_verdict"])
        critique = Critique.model_validate(state["critique"]) if state.get("critique") is not None else None
        if not draft.cover_letter.strip():
            return {"status": "needs_attention", "errors": ["Grounding left an empty proposal; no marketplace preview or submission attempted."]}
        blocking = list(compliance.blocking_reasons)
        if str(state.get('profile', {}).get('_marketplace_binding', '')).startswith('upwork:') and state['profile'].get('provenance') == 'synthetic':
            blocking.append('Synthetic demonstration profile cannot be used for a live Upwork proposal; provide your actual portfolio first')
        if not quote.affordable:
            blocking.append("insufficient Connects or over weekly Connects budget")
        dry = await deps.port.create_proposal_draft(
            preview_payload(state, draft), idempotency_key(state, draft), dry_run=True)
        payload = {
            "kind": "proposal_approval", "job": {"id": state["job_id"], "title": state["job"]["title"]},
            "draft": draft.model_dump(mode="json"),
            "claim_verification": [
                ClaimVerdict.model_validate(v).model_dump(mode="json")
                for v in state.get("claim_verification", [])
            ],
            "evidence": state["evidence"], "risk_report": risk.model_dump(mode="json"),
            "price_quote": quote.model_dump(mode="json"),
            "critique": critique.model_dump(mode="json") if critique is not None else None,
            "compliance_verdict": compliance.model_dump(mode="json"),
            "dry_run": dry, "blocking_reasons": blocking,
            "allowed_actions": ["edit", "reject"] if blocking else ["approve", "edit", "reject"],
        }
        edits = state.get("edit_history") or []
        if edits:
            payload["edit_diff"] = edits[-1]["diff"]
        while True:
            raw = interrupt(payload)
            decision = ApprovalDecision.model_validate(raw)
            if decision.action == "approve" and blocking:   # server-side enforcement, not just UI
                payload = {**payload, "error": "cannot approve while blocked", "allowed_actions": ["edit", "reject"]}
                continue
            break
        if decision.action == "edit":
            edited = decision.edited_cover_letter
            if edited is None:
                raise ValueError("an edit must include non-empty edited text")
            diff = "\n".join(difflib.unified_diff(draft.cover_letter.splitlines(), edited.splitlines(), lineterm=""))
            new = draft.model_copy(update={"edited_cover_letter": edited})
            return {"approval": decision, "proposal_draft": new,
                    "edit_history": [{"job_id": state["job_id"], "diff": diff, "original": draft.cover_letter,
                                     "edited": edited}]}
        status = "rejected" if decision.action == "reject" else ""
        return {"approval": decision, "status": status}
    return approval
