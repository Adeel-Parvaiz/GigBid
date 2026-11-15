"""WorkspaceService interface over the Workspace MCP server (same methods and return types as the local service)."""
from __future__ import annotations

from agent.mcp_client import AgentTools
from mcp_servers.workspace.tools import EmailDraftOut, HoldOut, SlotList


class McpWorkspace:
    def __init__(self, tools: AgentTools):
        self.tools = tools

    async def get_free_slots(self, start_date, days=5, duration_minutes=30, limit=5) -> SlotList:
        return SlotList(**await self.tools.call("liaison_calendar", "get_free_slots", {
            "start_date": start_date, "days": days, "duration_minutes": duration_minutes, "limit": limit}))

    async def create_tentative_hold(self, start, title, idempotency_key) -> HoldOut:
        return HoldOut(**await self.tools.call("approval_gate", "create_tentative_hold",
                                               {"start": start, "title": title, "idempotency_key": idempotency_key}))

    async def create_email_draft(self, to, subject, body, idempotency_key) -> EmailDraftOut:
        return EmailDraftOut(**await self.tools.call("approval_gate", "create_email_draft", {
            "to": to, "subject": subject, "body": body, "idempotency_key": idempotency_key}))
