from __future__ import annotations

import hmac
import re
from contextvars import ContextVar
from typing import Any

from starlette.responses import JSONResponse

portfolio_identity: ContextVar[tuple[str, str | None] | None] = ContextVar("portfolio_identity", default=None)


class PortfolioIdentityMiddleware:
    def __init__(self, app: Any, token: str):
        if not token:
            raise ValueError("PORTFOLIO_MCP_TOKEN is required for the HTTP portfolio MCP server")
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        user_id = headers.get(b"x-gigbid-user-id", b"").decode("latin-1")
        freelancer_id = headers.get(b"x-gigbid-freelancer-id", b"").decode("latin-1") or None
        if not hmac.compare_digest(authorization, f"Bearer {self.token}") or not re.fullmatch(r"[a-f0-9]{12}", user_id):
            await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
            return

        identity_token = portfolio_identity.set((user_id, freelancer_id))
        try:
            await self.app(scope, receive, send)
        finally:
            portfolio_identity.reset(identity_token)
