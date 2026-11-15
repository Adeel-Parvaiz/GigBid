from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.handoffs import ApprovalDecision  # noqa: F401  (request body for approvals)


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    freelancer_id: str = "sample-ai-engineer"      # persona choice at onboarding


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    user_id: str
    email: str
    freelancer_id: str
    display_name: str = ""


class TokenOut(BaseModel):
    token: str
    user: UserOut


class RunOut(BaseModel):
    run_id: str
    kind: Literal["bid", "conv"]
    target: str
    status: str
    trace_id: str
    degraded: bool = False
    created_at: float
    outcome: str | None = None


class RunDetail(RunOut):
    pending: dict[str, Any] | None = None
    summary: dict[str, Any] = {}


class ReplayIn(BaseModel):
    checkpoint_id: str = Field(min_length=1, max_length=200)
    node: str = Field(min_length=1, max_length=100)


class ParagraphRegenerationIn(BaseModel):
    claim_index: int = Field(ge=0, le=50)


class ParagraphRegenerationOut(BaseModel):
    text: str


class JobCard(BaseModel):
    job_id: str
    title: str
    description: str = ""
    client_id: str = ""
    connects_cost: int | None = None
    budget_max: float | None = None
    required_skills: list[str] = []
    latest_run: RunOut | None = None
    fit_score: float | None = None
    risk_score: float | None = None
    recommended_action: str | None = None
    price: float | None = None


class ThreadCard(BaseModel):
    thread_id: str
    job_id: str
    client_id: str
    last_message: str = ""
    latest_run: RunOut | None = None


class OutcomeIn(BaseModel):
    outcome: Literal["viewed", "replied", "interview", "hired", "lost"]


class PipelineOut(BaseModel):
    columns: dict[str, list[RunOut]]


class RunMetricOut(BaseModel):
    run_id: str
    target: str
    kind: Literal["bid", "conv"]
    status: str
    trace_id: str
    tokens_used: int
    input_tokens: int
    output_tokens: int
    output_tokens_per_second: float | None
    latency_ms: float | None
    cost_usd: float | None
    usage_exact: bool
    models: list[str]
    job_analyzed: bool
    proposal: bool


class AnalyticsOut(BaseModel):
    runs: int
    by_status: dict[str, int]
    connects_spent: int
    latency_ms_p50: float | None
    latency_ms_p95: float | None
    jobs_analyzed: int
    proposals: int
    average_tokens_per_job: float | None
    average_tokens_per_proposal: float | None
    average_output_tokens_per_second: float | None
    average_cost_per_proposal_usd: float | None
    priced_proposals: int
    unpriced_proposals: int
    billing: str
    hardware_note: str | None
    run_metrics: list[RunMetricOut]
    top_skip_reasons: list[tuple[str, int]]
    top_rejection_reasons: list[tuple[str, int]]
    reply_rate_by_category: dict[str, dict[str, Any]]


class MemoryOut(BaseModel):
    style: list[dict[str, Any]]
    outcome: dict[str, dict[str, Any]]


class HealthOut(BaseModel):
    api: str = "ok"
    marketplace: Literal["ok", "degraded"]
    queued_degraded_runs: int
