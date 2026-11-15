from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request


async def get_user(request: Request, authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    user = request.app.state.users.verify(token) if token else None
    if not user:
        raise HTTPException(401, "not authenticated")
    from agent.marketplace_context import marketplace_user
    marketplace_user.set(user['user_id'])
    return user


def get_run(run_id: str, request: Request, user: dict = Depends(get_user)) -> dict:
    run = request.app.state.manager.store.get(run_id)
    if not run or run["user_id"] != user["user_id"]:       # same 404 either way: no cross-tenant existence leak
        raise HTTPException(404, "run not found")
    return run
