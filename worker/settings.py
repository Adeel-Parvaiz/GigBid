"""Arq worker (Redis). Scouting and long runs happen here, never inside a web request.

Run: arq worker.settings.WorkerSettings
Idempotent by construction: the Redis job id is deterministic, the run store refuses a second live run for the
same (user, job), and the graph's own idempotency key stops double submits. A worker restart cannot double-analyse.
"""
from __future__ import annotations

import os
from contextlib import AsyncExitStack

from arq import cron
from arq.connections import RedisSettings

from agent.config import load_config
from agent.persistence import make_checkpointer, make_memory_store
from agent.runtime import build_deps
from apps.api.auth.users import UserStore
from apps.api.runs import RunManager, RunStore

CFG = load_config()
INTERVAL = int(os.environ.get("SCOUT_INTERVAL_MINUTES", CFG["worker"]["scout_interval_minutes"]))
LIVE_MIN_SCOUT_INTERVAL_MINUTES = 120


def _cron_jobs_for_interval(interval: int):
    if interval <= 0:
        raise ValueError("SCOUT_INTERVAL_MINUTES must be positive")
    if 60 % interval == 0:
        return [cron(scout_all, minute=set(range(0, 60, interval)), run_at_startup=False)]
    if 1440 % interval != 0:
        raise ValueError("SCOUT_INTERVAL_MINUTES must evenly divide an hour or a day")

    jobs = []
    for offset in range(0, 1440, interval):
        hour, minute = divmod(offset, 60)
        jobs.append(cron(
            scout_all,
            name=f"scout_all_{hour:02d}_{minute:02d}",
            hour=hour,
            minute=minute,
            run_at_startup=False,
        ))
    return jobs


def _live_scheduled_reads_allowed(interval: int, explicitly_enabled: bool) -> bool:
    return explicitly_enabled and interval >= LIVE_MIN_SCOUT_INTERVAL_MINUTES


async def startup(ctx):
    ctx["stack"] = AsyncExitStack()
    database_url = os.environ.get("DATABASE_URL")
    cp = await ctx["stack"].enter_async_context(make_checkpointer(database_url))
    memory_store = await ctx["stack"].enter_async_context(make_memory_store(database_url))
    ctx["manager"] = RunManager(build_deps(CFG, memory_store=memory_store), cp,
                                RunStore(os.environ.get("RUNS_DB", "runs.sqlite")), origin="worker")
    ctx["users"] = UserStore(os.environ.get("USERS_DB", ":memory:"))
    from apps.api.auth.upwork_oauth import UpworkOAuth
    from mcp_servers.marketplace.adapters.upwork_live import RoutedMarketplacePort
    ctx['upwork'] = UpworkOAuth()
    ctx['manager'].deps.port = RoutedMarketplacePort(ctx['manager'].deps.port, ctx['upwork'])


async def shutdown(ctx):
    if ctx.get('upwork'):
        await ctx['upwork'].close()
    await ctx["stack"].aclose()


async def analyse_job(ctx, user_id: str, job_id: str) -> dict:
    user = ctx["users"].get(user_id)
    if not user:
        return {"error": "unknown user"}
    run = await ctx["manager"].run_blocking(user, "bid", job_id)
    return {"run_id": run["run_id"], "status": run["status"]}


async def execute_queued_run(ctx, run_id: str) -> dict:
    manager = ctx["manager"]
    run = manager.store.get(run_id)
    if not run:
        return {"error": "unknown run"}
    user = ctx["users"].get(run["user_id"])
    if not user:
        reason = "run owner no longer exists"
        manager.store.update(run_id, status="dead_letter")
        manager.store.record_dead_letter(run_id, reason)
        return {"run_id": run_id, "status": "dead_letter", "error": reason}
    result = await manager.run_existing(run_id, user)
    return {"run_id": run_id, "status": result["status"]}


async def resume_queued_run(ctx, run_id: str, decision: dict) -> dict:
    manager = ctx["manager"]
    run = manager.store.get(run_id)
    if not run:
        return {"error": "unknown run"}
    user = ctx["users"].get(run["user_id"])
    if not user:
        reason = "run owner no longer exists"
        manager.store.update(run_id, status="dead_letter")
        manager.store.record_dead_letter(run_id, reason)
        return {"run_id": run_id, "status": "dead_letter", "error": reason}
    result = await manager.resume_blocking(run_id, user, decision)
    return {"run_id": run_id, "status": result["status"]}


async def continue_queued_run(ctx, run_id: str) -> dict:
    manager = ctx["manager"]
    run = manager.store.get(run_id)
    if not run:
        return {"error": "unknown run"}
    user = ctx["users"].get(run["user_id"])
    if not user:
        reason = "run owner no longer exists"
        manager.store.update(run_id, status="dead_letter")
        manager.store.record_dead_letter(run_id, reason)
        return {"run_id": run_id, "status": "dead_letter", "error": reason}
    result = await manager.retry_blocking(run_id, user)
    return {"run_id": result["run_id"], "status": result["status"]}


async def replay_queued_run(ctx, run_id: str, checkpoint_id: str, node: str) -> dict:
    manager = ctx["manager"]
    result = await manager.replay_blocking(run_id, checkpoint_id, node)
    return {"run_id": result["run_id"], "status": result["status"]}


async def scout(ctx, user_id: str, query: str) -> dict:
    """Read-only saved-search poll. Each NEW job becomes one deterministic analyse job."""
    m, new = ctx["manager"], []
    from agent.marketplace_context import marketplace_user
    live = ctx.get('upwork') and ctx['upwork'].vault.get(user_id, 'mode') in {'upwork', 'upwork_readonly'}
    if live and not _live_scheduled_reads_allowed(
        INTERVAL, os.environ.get("UPWORK_SCHEDULED_READS") == "1"
    ):
        return {
            "query": query,
            "enqueued": [],
            "note": (
                "Live scheduled reads disabled; explicit opt-in and interval >= "
                f"{LIVE_MIN_SCOUT_INTERVAL_MINUTES} minutes required"
            ),
        }
    token = marketplace_user.set(user_id)
    try:
        jobs = await m.deps.port.search_jobs(query, 20)
    finally:
        marketplace_user.reset(token)
    for job in jobs:
        if m.store.find_active(user_id, "bid", job["job_id"]):
            continue
        await ctx["redis"].enqueue_job("analyse_job", user_id, job["job_id"], _job_id=f"analyse:{user_id}:{job['job_id']}")
        new.append(job["job_id"])
    return {"query": query, "enqueued": new}


async def scout_all(ctx) -> int:
    from apps.api.recovery import recover_once
    await recover_once(ctx['manager'], ctx['users'])
    n = 0
    for user_id, query in ctx["manager"].store.searches():
        await scout(ctx, user_id, query)
        n += 1
    return n


class WorkerSettings:
    functions = [
        analyse_job,
        execute_queued_run,
        resume_queued_run,
        continue_queued_run,
        replay_queued_run,
        scout,
    ]
    cron_jobs = _cron_jobs_for_interval(INTERVAL)
    on_startup, on_shutdown = startup, shutdown
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    max_jobs, job_timeout, max_tries = 4, 300, 2
