from __future__ import annotations

from agent.deps import Deps
from agent.handoffs import BidDecision, FitReport, RiskReport


def make(deps: Deps):
    t = deps.cfg["thresholds"]

    async def decide(state):
        risk = RiskReport.model_validate(state["risk_report"])
        fit = FitReport.model_validate(state["fit_report"])
        prof = state["profile"]
        job_max = (state["job"].get("budget") or {}).get("max", 0)
        reasons: list[str] = []
        if risk.score > t["maximum_risk_score"]:
            reasons.append(f"risk {risk.score:.2f} > {t['maximum_risk_score']} ({', '.join(risk.flags)})")
        if state["job"].get("budget", {}).get("unit") == "hour":
            if job_max and job_max < 0.8 * prof.get("hourly_rate_usd", 0):
                reasons.append(f"client's top rate {job_max}/h is below 80% of your {prof['hourly_rate_usd']}/h")
        elif job_max and job_max < prof.get("minimum_project_budget_usd", 0):
            reasons.append(f"budget ceiling {job_max} below your minimum {prof['minimum_project_budget_usd']}")
        if reasons:
            action = "skip"
        elif fit.score >= t["minimum_fit_score"]:
            action, reasons = "bid", [f"fit {fit.score:.2f} >= {t['minimum_fit_score']}"]
        elif fit.score >= t["minimum_fit_score"] - t["watch_margin"]:
            action, reasons = "watch", [f"fit {fit.score:.2f} is borderline; missing {fit.missing_skills}"]
        else:
            # autonomy: auto_skip_low_fit=False keeps low-fit jobs visible as "watch" for a human look. It can never auto-send.
            action = "skip" if prof.get("auto_skip_low_fit", True) else "watch"
            reasons = [f"fit {fit.score:.2f} < {t['minimum_fit_score']}; missing {fit.missing_skills}"]
        d = BidDecision(action=action, reasons=reasons)
        return {"decision": d, "status": {"bid": "", "watch": "watching", "skip": "skipped"}[action]}
    return decide
