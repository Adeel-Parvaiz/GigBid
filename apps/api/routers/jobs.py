from fastapi import APIRouter, Depends, HTTPException, Request

from agent.marketplace_port import MarketplaceError
from apps.api.deps import get_user
from apps.api.dispatch import start_run
from apps.api.schemas import JobCard, RunOut

router = APIRouter(tags=["jobs"])


def _run_out(r: dict | None) -> RunOut | None:
    return RunOut(**{k: v for k, v in r.items() if k != "user_id"}) if r else None


@router.get("/jobs", response_model=list[JobCard])
async def inbox(request: Request, user: dict = Depends(get_user)):
    """Job inbox: new jobs, ranked by fit where a run has already analysed them."""
    m = request.app.state.manager
    try:
        jobs = await m.deps.port.search_jobs(None, 50)
    except MarketplaceError as e:
        raise HTTPException(503, 'The marketplace connection is temporarily unavailable. Any queued analyses resume after it recovers.') from e
    latest = {}
    for r in m.store.list(user["user_id"]):
        if r["kind"] == "bid":
            latest.setdefault(r["target"], r)
    cards = []
    for j in jobs:
        run = latest.get(j["job_id"])
        vals = await m.values(run) if run else {}
        cards.append(JobCard(
            job_id=j["job_id"], title=j["title"], description=j.get("description", ""),
            client_id=j.get("client_id", ""), connects_cost=j.get("connects_cost", 0),
            budget_max=(j.get("budget") or {}).get("max"), required_skills=j.get("required_skills", []),
            latest_run=_run_out(run), fit_score=(vals.get("fit_report") or {}).get("score"),
            risk_score=(vals.get("risk_report") or {}).get("score"),
            recommended_action=(vals.get("decision") or {}).get("action"),
            price=(vals.get("price_quote") or {}).get("amount")))
    return sorted(cards, key=lambda c: (c.fit_score is None, -(c.fit_score or 0)))


@router.post("/jobs/{job_id}/runs", response_model=RunOut, status_code=202)
async def analyse_job(job_id: str, request: Request, user: dict = Depends(get_user)):
    run = await start_run(request, user, "bid", job_id)
    return _run_out(run)
