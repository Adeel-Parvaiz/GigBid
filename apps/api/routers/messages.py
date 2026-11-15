from fastapi import APIRouter, Depends, HTTPException, Request

from agent.marketplace_port import MarketplaceError
from apps.api.deps import get_user
from apps.api.dispatch import start_run
from apps.api.routers.jobs import _run_out
from apps.api.schemas import RunOut, ThreadCard

router = APIRouter(prefix="/conversations", tags=["messages"])


@router.get("", response_model=list[ThreadCard])
async def threads(request: Request, user: dict = Depends(get_user)):
    m = request.app.state.manager
    try:
        ts = await m.deps.port.list_threads()
    except MarketplaceError as e:
        raise HTTPException(503, 'The marketplace connection is temporarily unavailable. Please retry after it recovers.') from e
    latest = {r["target"]: r for r in reversed(m.store.list(user["user_id"])) if r["kind"] == "conv"}
    return [ThreadCard(thread_id=t["thread_id"], job_id=t["job_id"], client_id=t["client_id"],
                       last_message=t.get("last_message", ""), latest_run=_run_out(latest.get(t["thread_id"]))) for t in ts]


@router.post("/{thread_id}/runs", response_model=RunOut, status_code=202)
async def handle_thread(thread_id: str, request: Request, user: dict = Depends(get_user)):
    return _run_out(await start_run(request, user, "conv", thread_id))
