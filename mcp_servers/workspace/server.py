from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_servers.workspace.tools import EmailDraftOut, HoldOut, Key, SlotList, WorkspaceService

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def build_server(svc: WorkspaceService | None = None, descriptions: dict[str, str] | None = None) -> FastMCP:
    if svc is None:
        from mcp_servers.workspace.persistent import PersistentWorkspaceService
        svc = PersistentWorkspaceService(os.environ.get('WORKSPACE_DB', Path(__file__).resolve().parents[2] / '.local-models/workspace/state.sqlite'))
    descriptions = descriptions or {}
    mcp = FastMCP("gigbid-workspace", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8002")))

    @mcp.tool(annotations=READ, description=descriptions.get(
        "get_free_slots", "List free interview slots on working days, starting at start_date (YYYY-MM-DD)."))
    async def get_free_slots(start_date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")],
                             days: Annotated[int, Field(ge=1, le=14)] = 5,
                             duration_minutes: Annotated[int, Field(ge=15, le=120)] = 30,
                             limit: Annotated[int, Field(ge=1, le=20)] = 5) -> SlotList:
        return await svc.get_free_slots(start_date, days, duration_minutes, limit)

    @mcp.tool(annotations=WRITE, description=descriptions.get(
        "create_tentative_hold", "Create a TENTATIVE calendar hold for an interview slot. Idempotent by key."))
    async def create_tentative_hold(start: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")],
                                    title: Annotated[str, Field(min_length=1, max_length=120)],
                                    idempotency_key: Key) -> HoldOut:
        return await svc.create_tentative_hold(start, title, idempotency_key)

    @mcp.tool(annotations=WRITE, description=descriptions.get(
        "create_email_draft", "Create an email DRAFT. It is never sent; the human sends it."))
    async def create_email_draft(to: Annotated[str, Field(max_length=200)],
                                 subject: Annotated[str, Field(min_length=1, max_length=200)],
                                 body: Annotated[str, Field(min_length=1, max_length=10000)],
                                 idempotency_key: Key) -> EmailDraftOut:
        return await svc.create_email_draft(to, subject, body, idempotency_key)
    return mcp


if __name__ == "__main__":
    import sys
    build_server().run(transport=sys.argv[1] if len(sys.argv) > 1 else "stdio")  # type: ignore[arg-type]
