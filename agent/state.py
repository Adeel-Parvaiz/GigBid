"""State = what this job needs *right now*. Trace = audit log. Memory = promoted knowledge (separate)."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from agent.handoffs import (
    ApprovalDecision,
    BidDecision,
    ClaimVerdict,
    ComplianceVerdict,
    Critique,
    FitReport,
    JobSpec,
    PriceQuote,
    ProposalDraft,
    RiskReport,
)


def merge_evidence(a: list[dict] | None, b: list[dict] | None) -> list[dict]:
    seen: dict[str, dict] = {}
    for item in (a or []) + (b or []):
        seen.setdefault(item["evidence_id"], item)
    return list(seen.values())


def last_nonempty(a: str | None, b: str | None) -> str:
    return b or a or ""


class BidState(TypedDict, total=False):
    # input
    job_id: str
    profile: dict[str, Any]
    # loaded
    job: dict[str, Any]
    client: dict[str, Any]
    # parallel branch outputs (each branch writes its own key; evidence has a reducer)
    job_spec: JobSpec
    risk_report: RiskReport
    fit_report: FitReport
    evidence: Annotated[list[dict[str, Any]], merge_evidence]
    # decision path
    decision: BidDecision
    price_quote: PriceQuote
    proposal_draft: ProposalDraft
    claim_verification: list[ClaimVerdict]
    verification_stats: dict[str, Any]
    critique: Critique
    revisions: int
    compliance_verdict: ComplianceVerdict
    approval: ApprovalDecision
    edit_history: Annotated[list[dict[str, Any]], operator.add]
    submission: dict[str, Any]
    # control
    status: Annotated[str, last_nonempty]
    steps: Annotated[int, operator.add]
    errors: Annotated[list[str], operator.add]
    tokens_used: Annotated[int, operator.add]
    llm_usage: Annotated[list[dict[str, Any]], operator.add]
    # execution trace (audit/debug only; never read by decision logic, never written to memory)
    trace: Annotated[list[dict[str, Any]], operator.add]
