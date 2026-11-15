"""Marketplace service: typed schemas, rate limit, PII-masked append-only audit log. Wraps any MarketplacePort."""
from __future__ import annotations

import contextvars
import json
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from agent.marketplace_port import MarketplaceError, MarketplacePort

current_user: contextvars.ContextVar[str] = contextvars.ContextVar("current_user", default="local")
current_trace: contextvars.ContextVar[str] = contextvars.ContextVar("current_trace", default="-")

Id = Annotated[str, Field(pattern=r"^[\w.-]{1,64}$", description="Opaque marketplace id")]
Key = Annotated[str, Field(min_length=8, max_length=64, description="Idempotency key: a retry with the same key never repeats the action")]


class ProposalInput(BaseModel):
    job_id: Id
    freelancer_id: Id | None = None
    cover_letter: Annotated[str, Field(min_length=1, max_length=5000)]
    screening_answers: Annotated[list[Annotated[str, Field(max_length=3000)]], Field(max_length=20)] = []
    bid_amount: Annotated[float, Field(gt=0, le=1_000_000)]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "USD"
    idempotency_key: Key
    dry_run: bool = Field(False, description="If true, nothing is created; returns exactly what would be sent and its Connects cost")


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


class JobOut(Loose):
    job_id: str
    title: str
    description: str = ""
    required_skills: list[str] = []
    connects_cost: int = 0


class JobList(BaseModel):
    jobs: list[JobOut]


class ClientOut(Loose):
    client_id: str
    completed_projects: int = 0
    payment_verified: bool = False


class BalanceOut(BaseModel):
    balance: int


class DraftOut(Loose):
    status: str = "draft"
    dry_run: bool = False
    draft_id: str | None = None
    would_send: dict[str, Any] | None = None
    connects_cost: int = 0
    replayed: bool = False


class SubmitOut(BaseModel):
    draft_id: str
    status: str
    connects_spent: int
    replayed: bool


class MessageOut(Loose):
    id: str
    text: str


class ThreadOut(Loose):
    thread_id: str
    messages: list[MessageOut]


class ThreadSummary(Loose):
    thread_id: str
    job_id: str
    client_id: str


class ThreadList(BaseModel):
    threads: list[ThreadSummary]


class SendOut(BaseModel):
    message_id: str
    thread_id: str
    replayed: bool


class RateLimited(ValueError):
    pass


class RateLimiter:
    """Per-user sliding window, kept under the marketplace's own limit."""
    def __init__(self, per_minute: int = 20, clock=time.monotonic):
        self.per_minute, self.clock, self.hits = per_minute, clock, defaultdict(deque)

    def check(self, user: str) -> None:
        now, q = self.clock(), self.hits[user]
        while q and now - q[0] >= 60:
            q.popleft()
        if len(q) >= self.per_minute:
            raise RateLimited(f"rate_limited: retry in {60 - (now - q[0]):.0f}s")
        q.append(now)


_PII = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"), (re.compile(r"\+?\d[\d\s().-]{8,}\d"), "[phone]")]


def mask(text: str) -> str:
    for rx, rep in _PII:
        text = rx.sub(rep, text)
    return text


class MarketplaceService:
    def __init__(self, adapter: MarketplacePort, audit_path: str | Path = "marketplace_audit.jsonl",
                 per_minute: int = 20, clock=time.monotonic):
        self.adapter, self.audit_path, self.limiter = adapter, Path(audit_path), RateLimiter(per_minute, clock)

    def _audit(self, tool: str, args: dict, outcome: str, result: Any) -> None:
        row = {"ts": time.time(), "user": current_user.get(), "trace_id": current_trace.get(), "tool": tool,
               "args": json.loads(mask(json.dumps(args, default=str))),
               "outcome": outcome, "result": mask(json.dumps(result, default=str))[:500]}
        with self.audit_path.open("a") as f:           # append-only: opened with "a", never rewritten
            f.write(json.dumps(row) + "\n")

    async def run(self, tool: str, args: dict, coro_fn):
        try:
            self.limiter.check(current_user.get())
            result = await coro_fn()
        except MarketplaceError as e:
            self._audit(tool, args, f"error:{e.code}", str(e))
            raise ValueError(str(e)) from e
        except RateLimited as e:
            self._audit(tool, args, "rate_limited", str(e))
            raise
        self._audit(tool, args, "ok", result)
        return result
