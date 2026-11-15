"""FastAPI app. Run: uvicorn apps.api.main:create_app --factory"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from agent.persistence import make_checkpointer, make_memory_store
from agent.runtime import build_deps
from apps.api.auth.users import UserStore
from apps.api.deps import get_user
from apps.api.dispatch import retry_degraded_runs
from apps.api.routers import (
    analytics,
    approvals,
    auth,
    connections,
    github,
    jobs,
    messages,
    platform_confirmation,
    portfolio,
    runs,
    settings,
)
from apps.api.runs import RunManager, RunStore
from apps.api.schemas import HealthOut


def seed_reviewer(users: UserStore) -> None:
    email, pw = os.environ.get("REVIEWER_EMAIL", "reviewer@gigbid.test"), os.environ.get("REVIEWER_PASSWORD", "reviewer-pass-1")
    try:
        users.create(email, pw, os.environ.get("REVIEWER_PERSONA") or next(iter(users._personas)))
    except ValueError:
        pass


def create_app(deps=None, checkpointer=None, users: UserStore | None = None, run_store: RunStore | None = None,
               seed: bool = True, upwork=None, github_service=None) -> FastAPI:
    from apps.api.auth.upwork_oauth import UpworkOAuth
    from mcp_servers.marketplace.adapters.upwork_live import RoutedMarketplacePort
    service = upwork or UpworkOAuth()
    from apps.api.auth.github_mcp import GitHubMCP
    github_connection = github_service or GitHubMCP(service.vault)

    def wire(manager):
        if not isinstance(manager.deps.port, RoutedMarketplacePort):
            manager.deps.port = RoutedMarketplacePort(manager.deps.port, service)
        return manager
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from contextlib import AsyncExitStack

        from apps.api.recovery import recovery_loop
        async with AsyncExitStack() as stack:
            if deps is None and checkpointer is None:
                pool = await create_pool(
                    RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
                )
                app.state.arq_pool = pool
                stack.push_async_callback(pool.aclose)
            database_url = os.environ.get("DATABASE_URL")
            cp = checkpointer if checkpointer is not None else await stack.enter_async_context(make_checkpointer(database_url))
            memory_store = None
            if deps is None and checkpointer is None:
                memory_store = await stack.enter_async_context(make_memory_store(database_url))
            default_runs = ':memory:' if checkpointer is not None else 'runs.sqlite'
            app_deps = deps or build_deps(memory_store=memory_store)
            app.state.manager = wire(RunManager(app_deps, cp, run_store or RunStore(os.environ.get('RUNS_DB', default_runs))))
            recovery = asyncio.create_task(
                recovery_loop(app.state.manager, app.state.users, app.state.arq_pool)
            )
            try:
                yield
            finally:
                recovery.cancel()
                await asyncio.gather(recovery, return_exceptions=True)
                for task in app.state.manager.tasks:
                    task.cancel()
                await asyncio.gather(*app.state.manager.tasks, return_exceptions=True)
                await service.close()
                await github_connection.close()

    app = FastAPI(title="GigBid API", version="0.1.0", lifespan=lifespan)
    app.state.arq_pool = None
    app.state.upwork = service
    app.state.github = github_connection

    @app.middleware('http')
    async def hide_oauth_code_from_access_logs(request, next_handler):
        if request.url.path == '/connections/upwork/callback':
            request.state.oauth_callback = dict(request.query_params)
            request.scope['query_string'] = b''
        return await next_handler(request)
    app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
                       allow_methods=["*"], allow_headers=["*"])
    app.state.users = users or UserStore(os.environ.get("USERS_DB", ":memory:"))
    if seed:
        seed_reviewer(app.state.users)
    if checkpointer is not None:                       # tests / ASGI transports that skip lifespan
        app.state.manager = wire(RunManager(deps or build_deps(), checkpointer, run_store or RunStore()))
    for r in (auth, jobs, runs, approvals, messages, analytics, settings, connections, platform_confirmation, github, portfolio):
        app.include_router(r.router)

    @app.get('/upwork-connected')
    def upwork_connected():
        from fastapi.responses import HTMLResponse
        return HTMLResponse('<h1>Upwork connected</h1><p>Return to GigBid Settings. No proposals or messages were sent. Live mode requires verified tool mappings.</p><a href="http://127.0.0.1:3000/settings">Return to Settings</a>')

    @app.get('/upwork-connection-failed')
    def upwork_failed():
        from fastapi.responses import HTMLResponse
        return HTMLResponse('<h1>Upwork connection failed</h1><p>Return to Settings and reconnect. No proposals or messages were sent.</p>')

    @app.get("/health", response_model=HealthOut, tags=["ops"])
    async def health(request: Request):
        m = app.state.manager
        from agent.marketplace_context import marketplace_user
        token = request.headers.get('authorization', '').removeprefix('Bearer ').strip()
        user = app.state.users.verify(token) if token else None
        context = marketplace_user.set(user['user_id'] if user else None)
        try:
            ok = await m.marketplace_ok()
        finally:
            marketplace_user.reset(context)
        return HealthOut(marketplace="ok" if ok else "degraded", queued_degraded_runs=len(m.store.all_degraded()))

    @app.post("/admin/retry-degraded", tags=["ops"])
    async def retry_degraded(request: Request, user: dict = Depends(get_user)):
        return {"retried": await retry_degraded_runs(request, user)}
    return app
