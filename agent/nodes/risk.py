"""Risk Assessor. A deterministic rule floor runs first; the LLM can only ADD risk, never lower it,
so an injected 'mark this safe' instruction cannot talk the score down."""
from __future__ import annotations

import re

from agent.deps import Deps
from agent.handoffs import RiskReport


def rule_report(job: dict, client: dict, cfg: dict) -> RiskReport:
    r = cfg["risk"]
    text = f"{job.get('title', '')} {job.get('description', '')}"
    flags = set(job.get("warning_signals", []))
    for flag, pattern in r["patterns"].items():
        if re.search(pattern, text, flags=re.MULTILINE):
            flags.add(flag)
    if not client.get("payment_verified", False):
        flags.add("payment_unverified")
    rating = client.get("average_rating")
    if rating is not None and rating < r["low_rating_below"]:
        flags.add("low_client_rating")
    if (job.get("budget") or {}).get("max", 0) == 0:
        flags.add("no_budget")
    score = min(1.0, sum(r["flag_weights"].get(f, 0.2) for f in flags))
    return RiskReport(score=score, flags=sorted(flags), explanation=f"rule flags: {sorted(flags)}")


def make(deps: Deps):
    async def risk(state):
        floor = rule_report(state["job"], state["client"], deps.cfg)
        llm = await deps.llm.structured("risk", RiskReport, {
            "job": state["job"], "client": state["client"], "rule_flags": floor.flags})
        flags = sorted(set(floor.flags) | set(llm.flags))
        if not deps.cfg["defences"]["risk_rule_floor"]:       # eval-only switch: LLM output taken at face value
            return {"risk_report": llm}
        final = RiskReport(score=max(floor.score, llm.score), flags=flags,
                           explanation=(floor.explanation + " | " + llm.explanation).strip(" |"))
        return {"risk_report": final}
    return risk
