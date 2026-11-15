"""Bearer-token auth for the HTTP endpoint. Tokens come from env MARKETPLACE_MCP_TOKENS='tok:user,tok2:user2'."""
from __future__ import annotations

import hmac
import os

from starlette.responses import JSONResponse

from mcp_servers.marketplace.tools import current_trace, current_user


def parse_tokens(raw: str | None = None) -> dict[str, str]:
    raw = os.environ.get("MARKETPLACE_MCP_TOKENS", "") if raw is None else raw
    return dict(p.split(":", 1) for p in raw.split(",") if ":" in p)


class BearerAuthMiddleware:
    def __init__(self, app, tokens: dict[str, str]):
        self.app, self.tokens = app, tokens

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        supplied = headers.get("authorization", "").removeprefix("Bearer ").strip()
        user = next((u for t, u in self.tokens.items() if hmac.compare_digest(t, supplied)), None) if supplied else None
        if user is None:
            return await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
        tu, tt = current_user.set(user), current_trace.set(headers.get("x-trace-id", "-"))
        try:
            await self.app(scope, receive, send)
        finally:
            current_user.reset(tu)
            current_trace.reset(tt)
