import statistics
from collections import Counter

from agent.llm import HeuristicLLM
from fastapi import APIRouter, Depends, Request

from apps.api.deps import get_user
from apps.api.routers.jobs import _run_out
from apps.api.schemas import AnalyticsOut, MemoryOut, OutcomeIn, PipelineOut

router = APIRouter(tags=["analytics"])
COLUMNS = ["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]
OUTCOME_TO_MEMORY = {"hired": "won", "replied": "replied", "interview": "replied", "lost": "ignored"}

def provider_api_cost(usage: list[dict], rates: dict, billing: str) -> float | None:
    if billing != "provider_api" or not usage:
        return None
    total = 0.0
    for call in usage:
        price = rates.get(call["model"])
        if not call.get("exact_usage") or price is None:
            return None
        total += (
            call["input_tokens"] * price["input"] + call["output_tokens"] * price["output"]
        ) / 1_000_000
    return total


def measured_output_rate(usage: list[dict]) -> tuple[float | None, int, float]:
    if not usage or not all(call.get("exact_usage") for call in usage):
        return None, 0, 0.0
    output_tokens = sum(int(call["output_tokens"]) for call in usage)
    duration_seconds = sum(float(call["duration_seconds"]) for call in usage)
    rate = output_tokens / duration_seconds if output_tokens and duration_seconds > 0 else None
    return rate, output_tokens, duration_seconds


@router.get("/pipeline", response_model=PipelineOut)
def pipeline(request: Request, user: dict = Depends(get_user)):
    cols: dict[str, list] = {c: [] for c in COLUMNS}
    for r in request.app.state.manager.store.list(user["user_id"]):
        if r["kind"] != "bid":
            continue
        col = r["outcome"] if r["outcome"] in COLUMNS else "submitted" if r["status"] == "submitted" else \
            "drafted" if r["status"] in {"awaiting_approval", "awaiting_platform_confirmation"} else None
        if col:
            cols[col].append(_run_out(r))
    return PipelineOut(columns=cols)


@router.post("/runs/{run_id}/outcome", status_code=204)
async def outcome(run_id: str, body: OutcomeIn, request: Request, user: dict = Depends(get_user)):
    """Marketplace event (viewed/replied/...): moves the card and feeds outcome memory through its promotion rule."""
    m = request.app.state.manager
    run = m.store.get(run_id)
    if not run or run["user_id"] != user["user_id"] or run["status"] != "submitted":
        from fastapi import HTTPException
        raise HTTPException(404, "no submitted run")
    m.store.update(run_id, outcome=body.outcome)
    if body.outcome in OUTCOME_TO_MEMORY and m.deps.memory:
        job = (await m.values(run)).get("job", {})
        await m.deps.memory.record_outcome(
            user["freelancer_id"],
            (job.get("required_skills") or ["general"])[0],
            OUTCOME_TO_MEMORY[body.outcome],
            event_id=run_id,
        )


@router.get("/analytics", response_model=AnalyticsOut)
async def analytics(request: Request, user: dict = Depends(get_user)):
    m, runs = request.app.state.manager, request.app.state.manager.store.list(user["user_id"])
    lat, spent, skip, rej = [], 0, Counter(), Counter()
    run_metrics = []
    job_tokens, proposal_tokens, proposal_costs = [], [], []
    measured_output_tokens = measured_output_seconds = 0.0
    llm_cfg = m.deps.cfg["llm"]
    profile = llm_cfg["profiles"][llm_cfg["profile"]]
    if isinstance(m.deps.llm, HeuristicLLM):
        billing = "test_backend"
        hardware_note = "Heuristic test backend; tokens are estimates and no model throughput or hardware cost is measured."
    else:
        billing = profile.get("billing", "provider_api")
        hardware_note = profile.get("hardware_note") if billing == "local" else None
    rates = llm_cfg.get("pricing", {}).get("usd_per_million_tokens", {})
    for r in runs:
        v = await m.values(r)
        trace = v.get("trace") or []
        latency_ms = sum(t["ms"] for t in trace) if trace else None
        if latency_ms is not None:
            lat.append(latency_ms)
        spent += (v.get("submission") or {}).get("connects_spent", 0)
        usage = v.get("llm_usage") or []
        total_tokens = int(v.get("tokens_used") or 0)
        cost_usd = provider_api_cost(usage, rates, billing)
        cost_complete = cost_usd is not None
        input_tokens = output_count = 0
        models = []
        for call in usage:
            model = call["model"]
            models.append(model)
            input_tokens += int(call["input_tokens"])
            output_count += int(call["output_tokens"])
        output_rate, measured_tokens, measured_seconds = measured_output_rate(usage)
        is_job = r["kind"] == "bid" and bool(v.get("job_spec"))
        is_proposal = r["kind"] == "bid" and bool(v.get("proposal_draft"))
        if is_job:
            job_tokens.append(total_tokens)
        if is_proposal:
            proposal_tokens.append(total_tokens)
            if cost_complete and cost_usd is not None:
                proposal_costs.append(cost_usd)
        measured_output_tokens += measured_tokens
        measured_output_seconds += measured_seconds
        usage_exact = bool(usage) and all(call.get("exact_usage") for call in usage)
        run_metrics.append({
            "run_id": r["run_id"], "target": r["target"], "kind": r["kind"], "status": r["status"],
            "trace_id": r["trace_id"], "tokens_used": total_tokens, "input_tokens": input_tokens,
            "output_tokens": output_count, "output_tokens_per_second": output_rate, "latency_ms": latency_ms,
            "cost_usd": cost_usd if cost_complete else None,
            "usage_exact": usage_exact,
            "models": sorted(set(models)),
            "job_analyzed": is_job, "proposal": is_proposal,
        })
        if (v.get("decision") or {}).get("action") == "skip":
            skip.update((v["decision"]["reasons"] or [""])[:1])
        if (v.get("approval") or {}).get("action") == "reject":
            rej.update([v["approval"].get("reason") or "no reason given"])
    q = statistics.quantiles(lat, n=20) if len(lat) >= 2 else lat
    reply_rate_by_category = (
        await m.deps.memory.outcome_memory(user["freelancer_id"]) if m.deps.memory else {}
    )
    return AnalyticsOut(runs=len(runs), by_status=dict(Counter(r["status"] for r in runs)), connects_spent=spent,
                        latency_ms_p50=statistics.median(lat) if lat else None, latency_ms_p95=(q[-1] if q else None),
                        jobs_analyzed=len(job_tokens), proposals=len(proposal_tokens),
                        average_tokens_per_job=statistics.mean(job_tokens) if job_tokens else None,
                        average_tokens_per_proposal=statistics.mean(proposal_tokens) if proposal_tokens else None,
                        average_output_tokens_per_second=(
                            measured_output_tokens / measured_output_seconds if measured_output_seconds else None
                        ),
                        average_cost_per_proposal_usd=(
                            statistics.mean(proposal_costs)
                            if proposal_tokens and len(proposal_costs) == len(proposal_tokens)
                            else None
                        ),
                        priced_proposals=len(proposal_costs), unpriced_proposals=len(proposal_tokens) - len(proposal_costs),
                        billing=billing, hardware_note=hardware_note, run_metrics=run_metrics,
                        top_skip_reasons=skip.most_common(5), top_rejection_reasons=rej.most_common(5),
                        reply_rate_by_category=reply_rate_by_category)


@router.get("/memory", response_model=MemoryOut)
async def memory(request: Request, user: dict = Depends(get_user)):
    mem = request.app.state.manager.deps.memory
    return MemoryOut(
        style=await mem.list_style(user["freelancer_id"]),
        outcome=await mem.outcome_memory(user["freelancer_id"]),
    )


@router.delete("/memory/style/{rule_id}", status_code=204)
async def forget_style(rule_id: str, request: Request, user: dict = Depends(get_user)):
    await request.app.state.manager.deps.memory.delete_style(user["freelancer_id"], rule_id)


@router.delete("/memory/outcome/{category}", status_code=204)
async def forget_outcome(category: str, request: Request, user: dict = Depends(get_user)):
    await request.app.state.manager.deps.memory.delete_outcome(user["freelancer_id"], category)
