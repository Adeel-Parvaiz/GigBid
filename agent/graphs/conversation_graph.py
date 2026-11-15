"""Conversation graph (one thread per client conversation): classify -> (slots) -> draft -> approve -> send."""
from __future__ import annotations

import asyncio
import time

from langgraph.graph import END, START, StateGraph

from agent.deps import Deps
from agent.handoffs import ApprovalDecision
from agent.nodes import liaison as L
from agent.nodes.learn import make as make_learn
from agent.resilience import node_runtime_options
from agent.state_conv import ConvState
from agent.token_budget import TokenBudget, TokenBudgetExceeded, current_token_budget

TERMINAL = {"error", "needs_attention", "flagged"}


def _instrument(name, fn, max_steps, max_tokens, timeout_seconds):
    async def inner(state):
        if state.get("status") in TERMINAL:
            return {}
        if state.get("steps", 0) >= max_steps:
            return {"status": "needs_attention", "errors": [f"step budget exceeded at {name}"]}
        token_limit = max_tokens
        tokens_used = int(state.get("tokens_used", 0))
        if tokens_used > token_limit:
            return {"status": "needs_attention",
                    "errors": [f"token budget {token_limit} reached before {name} ({tokens_used} tokens used)"]}
        tracker = TokenBudget(token_limit, tokens_used, name)
        token = current_token_budget.set(tracker)
        t0 = time.perf_counter()
        try:
            out = dict(await asyncio.wait_for(fn(state), timeout_seconds))
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
        out["trace"] = [{"node": name, "ms": round((time.perf_counter() - t0) * 1000, 1)}]
        return out
    return inner


def build_conversation_graph(deps: Deps, checkpointer=None):
    m = deps.cfg["budgets"]["max_graph_steps"]
    max_tokens = deps.cfg["budgets"]["max_tokens_per_job"]
    g = StateGraph(ConvState)
    for name, fn in {"load_thread": L.make_load(deps), "classify": L.make_classify(deps),
                     "propose_slots": L.make_slots(deps), "draft_reply": L.make_reply(deps),
                     "compliance": L.make_compliance(deps), "approval": L.make_approval(deps),
                     "send_reply": L.make_send(deps), "learn": make_learn(deps)}.items():
        options = node_runtime_options(deps.cfg, name)
        g.add_node(name, _instrument(name, fn, m, max_tokens, options["timeout_seconds"]),
                   retry_policy=options["retry_policy"])
    g.add_edge(START, "load_thread")
    g.add_conditional_edges("load_thread", lambda s: END if s.get("status") in TERMINAL else "classify", ["classify", END])
    g.add_conditional_edges("classify", lambda s: END if s.get("status") in TERMINAL else "propose_slots", ["propose_slots", END])
    g.add_edge("propose_slots", "draft_reply")
    g.add_conditional_edges("draft_reply", lambda s: END if s.get("status") in TERMINAL else "compliance",
                            ["compliance", END])
    g.add_conditional_edges("compliance", lambda s: END if s.get("status") in TERMINAL else "approval",
                            ["approval", END])
    g.add_edge("send_reply", "learn")
    g.add_edge("learn", END)
    g.add_conditional_edges(
        "approval",
        lambda s: END if s.get("status") in TERMINAL else {
            "approve": "send_reply", "edit": "compliance", "reject": END
        }[ApprovalDecision.model_validate(s["approval"]).action],
        ["send_reply", "compliance", END],
    )
    return g.compile(checkpointer=checkpointer)
