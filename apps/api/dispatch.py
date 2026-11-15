from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request
from redis.exceptions import RedisError

from apps.api.runs import RunManager


async def _enqueue(request: Request, run: dict, function: str, *args, job_id: str) -> None:
    manager: RunManager = request.app.state.manager
    try:
        await request.app.state.arq_pool.enqueue_job(
            function, *args, _job_id=job_id
        )
    except (RedisError, OSError, TimeoutError) as error:
        manager.store.update(run["run_id"], status="dead_letter")
        manager.store.record_dead_letter(
            run["run_id"], f"Could not enqueue work: {type(error).__name__}"
        )
        raise HTTPException(503, "The run worker is unavailable; this run needs attention.") from error


async def start_run(request: Request, user: dict, kind: str, target: str) -> dict:
    manager: RunManager = request.app.state.manager
    pool = request.app.state.arq_pool
    if pool is None:
        return await manager.start(user, kind, target)

    run, _ = await manager.prepare_worker(user, kind, target)
    if run["origin"] == "worker" and run["status"] == "running":
        await _enqueue(request, run, "execute_queued_run", run["run_id"], job_id=f"run:{run['run_id']}")
    return run


async def resume_run(request: Request, run: dict, decision: dict) -> dict:
    manager: RunManager = request.app.state.manager
    pool = request.app.state.arq_pool
    if pool is None:
        await manager.resume(run, decision)
        return run

    if not manager.store.claim_status(
        run["run_id"], run["user_id"], "awaiting_approval", "running"
    ):
        raise HTTPException(409, "this approval has already been queued or completed")
    await _enqueue(
        request, run, "resume_queued_run", run["run_id"], decision,
        job_id=f"resume:{run['run_id']}:{manager.store.last_event_seq(run['run_id'])}",
    )
    return manager.store.get(run["run_id"])


async def retry_run(request: Request, run: dict, user: dict) -> dict:
    manager: RunManager = request.app.state.manager
    if request.app.state.arq_pool is None:
        return await manager.retry(run, user)

    snapshot = await manager.graphs[run["kind"]].aget_state(manager.cfg(run["run_id"]))
    if not snapshot.next:
        manager.store.update(run["run_id"], status="superseded", degraded=False)
        return await start_run(request, user, run["kind"], run["target"])
    if not manager.store.claim_status(
        run["run_id"], user["user_id"], run["status"], "running"
    ):
        raise HTTPException(409, "this run has already been queued for retry")
    await _enqueue(
        request, run, "continue_queued_run", run["run_id"],
        job_id=f"retry:{run['run_id']}:{manager.store.last_event_seq(run['run_id'])}",
    )
    return manager.store.get(run["run_id"])


async def replay_run(request: Request, run: dict, checkpoint_id: str, node: str) -> dict:
    manager: RunManager = request.app.state.manager
    if request.app.state.arq_pool is None:
        return await manager.replay(run, checkpoint_id, node)

    await manager._replay_config(run, checkpoint_id, node)
    if not manager.store.claim_status(
        run["run_id"], run["user_id"], run["status"], "running"
    ):
        raise HTTPException(409, "this run has already been queued for replay")
    identity = hashlib.sha256(f"{checkpoint_id}:{node}".encode()).hexdigest()[:16]
    await _enqueue(
        request, run, "replay_queued_run", run["run_id"], checkpoint_id, node,
        job_id=f"replay:{run['run_id']}:{manager.store.last_event_seq(run['run_id'])}:{identity}",
    )
    return manager.store.get(run["run_id"])


async def retry_degraded_runs(request: Request, user: dict) -> int:
    manager: RunManager = request.app.state.manager
    pool = request.app.state.arq_pool
    if pool is None:
        return await manager.retry_degraded(user)
    retried = 0
    for run in manager.store.all_degraded():
        if run["user_id"] == user["user_id"]:
            await retry_run(request, run, user)
            retried += 1
    return retried
