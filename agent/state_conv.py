from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from agent.handoffs import (
    ApprovalDecision,
    ClaimVerdict,
    ComplianceVerdict,
    IntentResult,
    ReplyDraft,
)
from agent.state import last_nonempty


class ConvState(TypedDict, total=False):
    thread_id: str
    job_id: str
    profile: dict[str, Any]
    thread: dict[str, Any]
    intent: IntentResult
    evidence: list[dict[str, Any]]
    slots: list[str]
    reply: ReplyDraft
    claim_verification: list[ClaimVerdict]
    compliance_verdict: ComplianceVerdict
    approval: ApprovalDecision
    edit_history: Annotated[list[dict[str, Any]], operator.add]
    send_result: dict[str, Any]
    verification_stats: dict[str, Any]
    status: Annotated[str, last_nonempty]
    steps: Annotated[int, operator.add]
    tokens_used: Annotated[int, operator.add]
    llm_usage: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]
    trace: Annotated[list[dict[str, Any]], operator.add]
