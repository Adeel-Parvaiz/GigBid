from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from apps.api.deps import get_run, get_user
from apps.api.dispatch import replay_run, retry_run
from apps.api.routers.jobs import _run_out
from apps.api.schemas import ReplayIn, RunDetail, RunOut

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[RunOut])
def list_runs(request: Request, user: dict = Depends(get_user)):
    return [_run_out(r) for r in request.app.state.manager.store.list(user["user_id"])]


@router.get("/dead-letters")
def dead_letters(request: Request, user: dict = Depends(get_user)):
    return request.app.state.manager.store.list_dead_letters(user["user_id"])


@router.get("/{run_id}", response_model=RunDetail)
async def run_detail(request: Request, run: dict = Depends(get_run)):
    m = request.app.state.manager
    v = await m.values(run)
    summary = {k: v.get(k) for k in ("job_spec", "risk_report", "fit_report", "decision", "price_quote", "critique",
                                      "compliance_verdict", "claim_verification", "verification_stats", "evidence",
                                      "submission", "intent", "send_result", "errors", "tokens_used", "llm_usage")}
    summary["trace"] = v.get("trace", [])
    if run["status"] == "dead_letter":
        summary["failure_reason"] = m.store.dead_letter_reason(run["run_id"])
    return RunDetail(**{k: x for k, x in run.items() if k != "user_id"}, pending=await m.pending(run), summary=summary)


@router.get("/{run_id}/history")
async def checkpoint_history(request: Request, run: dict = Depends(get_run)):
    return await request.app.state.manager.history(run)


@router.post("/{run_id}/replay", response_model=RunOut, status_code=202)
async def replay(request: Request, body: ReplayIn, run: dict = Depends(get_run)):
    try:
        return _run_out(await replay_run(request, run, body.checkpoint_id, body.node))
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/{run_id}/events")
async def run_events(request: Request, run: dict = Depends(get_run), after: int = Query(0, ge=0)):
    """Server-Sent Events: node-by-node progress; the stream ends at an approval gate or when the run is done."""
    return StreamingResponse(request.app.state.manager.stream(run, after), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{run_id}/retry", response_model=RunOut, status_code=202)
async def retry(request: Request, run: dict = Depends(get_run), user: dict = Depends(get_user)):
    return _run_out(await retry_run(request, run, user))
