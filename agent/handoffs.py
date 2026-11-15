"""Typed hand-offs between agents. Anything a later step *decides on* is one of these."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator


class JobSpec(BaseModel):
    job_id: str
    title: str
    deliverables: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None
    duration_days: int | None = None
    screening_questions: list[str] = Field(default_factory=list)
    hidden_needs: list[str] = Field(default_factory=list)


class RiskReport(BaseModel):
    score: float = Field(ge=0, le=1)
    flags: list[str] = Field(default_factory=list)
    explanation: str = ""


class RequirementEvidence(BaseModel):
    requirement: str
    evidence_ids: list[str] = Field(default_factory=list)
    matched: bool = False


class FitReport(BaseModel):
    score: float = Field(ge=0, le=1)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    requirement_evidence: list[RequirementEvidence] = Field(default_factory=list)
    variant: str = ""


class BidDecision(BaseModel):
    action: Literal["bid", "watch", "skip"]
    reasons: list[str] = Field(default_factory=list)


class PriceQuote(BaseModel):
    amount: float
    currency: str = "USD"
    rationale: str
    connects_cost: int = 0
    affordable: bool = True


class Claim(BaseModel):
    """One sentence of a proposal. `boilerplate` = no experience claimed (greeting, closing)."""
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    kind: Literal["claim", "boilerplate", "logistics"] = "claim"   # logistics: written by code from tool data, never by the LLM
    section: str = "cover"  # "cover" or "screening:<question index>"


class ProposalDraft(BaseModel):
    job_id: str
    questions: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    edited_cover_letter: str | None = None  # set when the human edits the text

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cover_letter(self) -> str:
        if self.edited_cover_letter is not None:
            return self.edited_cover_letter
        return "\n\n".join(c.text for c in self.claims if c.section == "cover")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def screening_answers(self) -> list[str]:
        return [
            " ".join(c.text for c in self.claims if c.section == f"screening:{i}")
            for i in range(len(self.questions))
        ]


class ParagraphRewrite(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1)


class ClaimVerdict(BaseModel):
    text: str
    section: str
    label: Literal["supported", "partly_supported", "unsupported"]
    support: float
    reason: str = ""


class Critique(BaseModel):
    passed: bool
    score: float = Field(ge=0, le=1)
    issues: list[str] = Field(default_factory=list)


class Violation(BaseModel):
    rule: str
    match: str
    action: str


class ComplianceVerdict(BaseModel):
    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)


class ApprovalDecision(BaseModel):
    """What the web UI sends back to resume the interrupted thread."""
    action: Literal["approve", "edit", "reject"]
    edited_cover_letter: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> ApprovalDecision:
        if self.action == "edit" and (self.edited_cover_letter is None or not self.edited_cover_letter.strip()):
            raise ValueError("an edit must include non-empty edited text")
        if self.action == "reject":
            if self.reason is None or not self.reason.strip():
                raise ValueError("a rejection must include a reason")
            self.reason = self.reason.strip()
        return self


class IntentResult(BaseModel):
    intent: Literal["question", "negotiation", "interview_request", "scam_signal"]
    rationale: str = ""
    flags: list[str] = Field(default_factory=list)


class ReplyDraft(BaseModel):
    thread_id: str
    claims: list[Claim] = Field(default_factory=list)
    offered_slots: list[str] = Field(default_factory=list)
    edited_text: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def text(self) -> str:
        if self.edited_text is not None:
            return self.edited_text
        return " ".join(c.text for c in self.claims)
