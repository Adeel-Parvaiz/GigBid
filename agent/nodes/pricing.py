from __future__ import annotations

from agent.deps import Deps
from agent.handoffs import PriceQuote


def make(deps: Deps):
    async def pricing(state):
        job, prof = state["job"], state["profile"]
        b = job.get("budget") or {}
        lo, hi = b.get("min", 0), b.get("max", 0)
        floor = prof.get("minimum_project_budget_usd", 0)
        if b.get("unit") == "hour":
            rate = prof.get("hourly_rate_usd", 0)
            amount = min(max(rate, lo), hi) if hi else rate
            why = f"hourly: your rate {rate}/h" + (f" clamped to the client's range {lo}-{hi}/h" if hi else "; client gave no range")
        elif hi:
            amount = min(max((lo + hi) / 2, floor), hi)
            why = f"midpoint of client budget {lo}-{hi}, floored at your minimum {floor}"
        else:
            hours = deps.cfg["pricing"]["default_hours_per_day"] * (job.get("duration_days") or 5)
            amount = max(prof.get("hourly_rate_usd", 0) * hours, floor)
            why = f"no budget given; {hours}h at {prof.get('hourly_rate_usd')}/h, floored at {floor}"
        cost = int(job.get("connects_cost", 0))
        balance = (await deps.port.get_connects_balance())["balance"]
        weekly = prof.get("weekly_connects_budget")
        affordable = cost <= balance and (weekly is None or cost <= weekly)
        q = PriceQuote(amount=round(amount, 2), currency=b.get("currency", "USD"), rationale=why,
                       connects_cost=cost, affordable=affordable)
        return {"price_quote": q}
    return pricing
