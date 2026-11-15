"""MarketplacePort over the Marketplace MCP server. The graph cannot tell this from the sample/GigSim adapter."""
from __future__ import annotations

import os
from typing import Any

from agent.marketplace_port import MarketplaceError
from agent.mcp_client import AgentTools, McpUnavailable, ToolCallError

CODES = ("insufficient_connects", "job_not_found", "draft_not_found", "thread_not_found", "rate_limited")


class McpMarketplacePort:
    def __init__(self, tools: AgentTools):
        self.tools = tools

    async def _call(self, role: str, tool: str, args: dict[str, Any]) -> Any:
        try:
            return await self.tools.call(role, tool, args)
        except McpUnavailable as e:
            raise MarketplaceError("marketplace_unavailable", str(e)) from e
        except ToolCallError as e:
            raise MarketplaceError(next((c for c in CODES if c in str(e)), "tool_error"), str(e)) from e

    async def search_jobs(self, query=None, limit=20):
        return (await self._call("scout", "search_jobs", {"query": query, "limit": limit}))["jobs"]

    async def get_job(self, job_id):
        return await self._call("load_job", "get_job", {"job_id": job_id})

    async def get_client_history(self, client_id):
        return await self._call("load_job", "get_client_history", {"client_id": client_id})

    async def get_connects_balance(self):
        return await self._call("pricing", "get_connects_balance", {})

    async def create_proposal_draft(self, payload, idempotency_key, dry_run=False):
        proposal = {**payload, "idempotency_key": idempotency_key, "dry_run": dry_run}
        role = "approval_preview" if dry_run else "approval_gate"
        return await self._call(role, "create_proposal_draft", {"proposal": proposal})

    async def submit_proposal(self, draft_id, idempotency_key):
        return await self._call("approval_gate", "submit_proposal",
                                {"draft_id": draft_id, "idempotency_key": idempotency_key})

    async def list_threads(self):
        return (await self._call("liaison", "list_threads", {}))["threads"]

    async def list_messages(self, thread_id):
        return await self._call("liaison", "list_messages", {"thread_id": thread_id})

    async def send_message(self, thread_id, text, idempotency_key):
        return await self._call("approval_gate", "send_message",
                                {"thread_id": thread_id, "text": text, "idempotency_key": idempotency_key})


def build_mcp_port(cfg: dict, timeout: float = 15.0, retries: int = 2) -> McpMarketplacePort:
    m = cfg["marketplace"]
    token = os.environ.get(m.get("token_env", "MARKETPLACE_MCP_TOKEN"), "")
    conn = {"transport": "streamable_http", "url": m["url"], "headers": {"Authorization": f"Bearer {token}"}}
    return McpMarketplacePort(AgentTools({"marketplace": conn}, timeout=timeout, retries=retries))
