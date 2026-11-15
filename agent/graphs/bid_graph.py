"""Bid graph (one thread per job). Hand-written StateGraph; no prebuilt agent.

load_job -> [analyst | risk | fit_matcher] (parallel via Send) -> decide
  skip/watch -> END
  bid -> pricing -> writer -> verifier -> critic -(fail, <max_revisions)-> writer
                                            critic -> compliance -> approval(interrupt)
  approval: approve -> submit -> END | edit -> compliance -> approval | reject -> END
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agent.deps import Deps
from agent.handoffs import ApprovalDecision, BidDecision, Critique
from agent.nodes import (
    analyst,
    approval,
    compliance,
    critic,
    decide,
    fit_matcher,
    learn,
    load_job,
    pricing,
    risk,
    submit,
    verifier,
    writer,
)
from agent.resilience import node_runtime_options
from agent.state import BidState
from agent.token_budget import TokenBudget, TokenBudgetExceeded, current_token_budget

PARALLEL = ("analyst", "risk", "fit_matcher")
TERMINAL = {"error", "needs_attention"}


def _instrument(name: str, fn: Callable[[dict], Awaitable[dict]], max_steps: int, max_tokens: int,
                timeout_seconds: float):
    """Enforce per-thread budgets and append a trace entry for each node."""
    async def inner(state: dict) -> dict:
        if state.get("status") in TERMINAL:
            return {}
        if state.get("steps", 0) >= max_steps:
            return {"status": "needs_attention", "errors": [f"step budget {max_steps} exceeded at {name}"]}
        token_limit = max_tokens
        tokens_used = int(state.get("tokens_used", 0))
        if tokens_used > token_limit:
            return {"status": "needs_attention",
                    "errors": [f"token budget {token_limit} reached before {name} ({tokens_used} tokens used)"]}
        tracker = TokenBudget(token_limit, tokens_used, name)
        token = current_token_budget.set(tracker)
        t0 = time.perf_counter()
        try:
            out: dict[str, Any] = dict(await asyncio.wait_for(fn(state), timeout_seconds))
        except TokenBudgetExceeded as error:
            out = {"status": "needs_attention", "errors": [str(error)]}
        finally:
            current_token_budget.reset(token)
        if tracker.used_here:
            out["tokens_used"] = tracker.used_here
            total_used = tokens_used + tracker.used_here
            if total_used > token_limit:
                out["status"] = "needs_attention"
                out.setdefault("errors", []).append(
                    f"token budget {token_limit} exceeded at {name} ({total_used} tokens used)"
                )
        if tracker.usage:
            out["llm_usage"] = tracker.usage
        out["steps"] = 1
        out["trace"] = [{"node": name, "ms": round((time.perf_counter() - t0) * 1000, 1),
                         "wrote": sorted(k for k in out if k not in ("steps", "trace"))}]
        return out
    return inner


def build_bid_graph(deps: Deps, checkpointer=None):
    cfg = deps.cfg
    max_steps, max_rev = cfg["budgets"]["max_graph_steps"], cfg["budgets"]["max_revisions"]
    max_tokens = cfg["budgets"]["max_tokens_per_job"]
    factories = {"load_job": load_job, "analyst": analyst, "risk": risk, "fit_matcher": fit_matcher,
                 "decide": decide, "pricing": pricing, "writer": writer, "verifier": verifier,
                 "critic": critic, "compliance": compliance, "approval": approval, "submit": submit, "learn": learn}
    g = StateGraph(BidState)
    for name, mod in factories.items():
        options = node_runtime_options(cfg, name)
        g.add_node(name, _instrument(name, mod.make(deps), max_steps, max_tokens, options["timeout_seconds"]),
                   retry_policy=options["retry_policy"])

    def fan_out(state):
        if state.get("status") in TERMINAL:
            return END
        return [Send(n, state) for n in PARALLEL]

    def after_decide(state):
        if state.get("status") in TERMINAL or BidDecision.model_validate(state["decision"]).action != "bid":
            return END
        return "pricing"

    def after_critic(state):
        if state.get("status") in TERMINAL:
            return END
        if not Critique.model_validate(state["critique"]).passed and state.get("revisions", 0) < max_rev:
            return "writer"
        return "compliance"

    def after_approval(state):
        if state.get("status") in TERMINAL:
            return END
        action = ApprovalDecision.model_validate(state["approval"]).action
        return {"approve": "submit", "edit": "compliance", "reject": END}[action]

    g.add_edge(START, "load_job")
    g.add_conditional_edges("load_job", fan_out, [*PARALLEL, END])
    for n in PARALLEL:
        g.add_edge(n, "decide")
    g.add_conditional_edges("decide", after_decide, ["pricing", END])
    for a, b in (("pricing", "writer"), ("writer", "verifier"), ("verifier", "critic"),
                 ("compliance", "approval"), ("submit", "learn"), ("learn", END)):
        g.add_edge(a, b)
    g.add_conditional_edges("critic", after_critic, ["writer", "compliance", END])
    g.add_conditional_edges("approval", after_approval, ["submit", "compliance", END])
    return g.compile(checkpointer=checkpointer)


async def pending_approval(graph, config) -> dict | None:
    """What a page refresh calls: the approval payload for a paused thread, if any."""
    snap = await graph.aget_state(config)
    for t in snap.tasks:
        for i in t.interrupts:
            return i.value
    return None
