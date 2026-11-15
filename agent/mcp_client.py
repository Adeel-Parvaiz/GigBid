"""MultiServerMCPClient setup with per-agent tool allowlists, timeouts and bounded retries (A6).

Errors from tools RAISE (handle_tool_errors=False). The adapter default turns a tool error into a
normal text result, which an agent could mistake for evidence.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import anyio
import httpx
from langchain_core.tools import ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.tracing import current_trace_id

# Each agent gets only the tools it needs, filtered by name.
ALLOWLIST: dict[str, set[str]] = {
    "scout": {"search_jobs"},
    "load_job": {"get_job", "get_client_history"},
    "pricing": {"get_connects_balance"},
    "liaison": {"list_messages", "list_threads"},
    "liaison_calendar": {"get_free_slots"},
    "approval_preview": {"create_proposal_draft"},                       # dry_run only, by construction
    "approval_gate": {"create_proposal_draft", "submit_proposal", "send_message", "create_tentative_hold", "create_email_draft"},  # only after a human approved
    "fit_matcher": {"search_evidence"},
    "writer": {"search_evidence", "get_case_study"},
    "verifier": {"search_evidence"},
    "critic": {"search_evidence"},
}


class McpUnavailable(RuntimeError):
    """Server unreachable/timed out after retries -> caller shows degraded mode, queues work."""


class ToolCallError(RuntimeError):
    """The server answered with a tool error (bad arguments, unknown id...). Not retried."""


MUTATING = {'create_proposal_draft', 'submit_proposal', 'send_message', 'create_tentative_hold', 'create_email_draft'}


def transport_error(error):
    """MCP HTTP transports wrap connection failures in AnyIO exception groups."""
    if isinstance(error, BaseExceptionGroup):
        return bool(error.exceptions) and all(transport_error(e) for e in error.exceptions)
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {408, 429, 500, 502, 503, 504}
    return isinstance(error, (TimeoutError, ConnectionError, OSError, httpx.TransportError,
                              anyio.EndOfStream, anyio.BrokenResourceError, anyio.ClosedResourceError))


def portfolio_connection(cfg: dict, user: str | None = None, freelancer: str | None = None) -> dict:
    p = cfg.get("portfolio", {})
    if p.get("transport") == "streamable_http":
        return {"transport": "streamable_http", "url": p["url"]}
    env = {k: os.environ[k] for k in ['PORTFOLIO_DIR', 'GIGBID_DATA_DIR', 'OAUTH_DB', 'OAUTH_ENCRYPTION_KEY'] if os.environ.get(k)}
    rag = cfg.get('rag', {})
    env['PORTFOLIO_RAG_CONFIG'] = json.dumps(rag)
    if user:
        env['PORTFOLIO_USER_ID'] = user
    if freelancer:
        env['PORTFOLIO_FREELANCER_ID'] = freelancer
    return {"transport": "stdio", "command": sys.executable, "args": ["-m", "mcp_servers.portfolio.server"], 'env': env}


def user_portfolio_search(cfg):
    async def search(query, k, filters=None):
        from agent.marketplace_context import marketplace_user
        connection = portfolio_connection(cfg, marketplace_user.get(), (filters or {}).get('freelancer_id'))
        tools = AgentTools({'portfolio': connection})
        return await mcp_search_fn(tools)(query, k, filters)
    return search


def workspace_connection(cfg: dict) -> dict:
    workspace = cfg['workspace']
    if workspace.get('transport', 'streamable_http') == 'streamable_http':
        return {'transport': 'streamable_http', 'url': workspace['url']}
    if workspace['transport'] == 'stdio':
        return {'transport': 'stdio', 'command': sys.executable,
                'args': ['-m', 'mcp_servers.workspace.server'],
                'env': {'WORKSPACE_DB': os.environ['WORKSPACE_DB']} if os.environ.get('WORKSPACE_DB') else {}}
    raise ValueError('Workspace transport must be stdio or streamable_http')


async def trace_interceptor(request, handler):
    """Stamp every MCP call with the current trace id (HTTP transports)."""
    return await handler(request.override(headers={**(request.headers or {}), "X-Trace-Id": current_trace_id.get()}))


class AgentTools:
    def __init__(self, connections: dict[str, dict], timeout: float = 15.0, retries: int = 2,
                 backoff: float = 0.3, allowlist: dict[str, set[str]] | None = None):
        self.client = MultiServerMCPClient(connections, handle_tool_errors=False, tool_interceptors=[trace_interceptor])
        if timeout <= 0 or not 0 <= retries <= 5 or backoff < 0:
            raise ValueError('Positive timeout, zero-to-five retries and nonnegative backoff required')
        self.timeout, self.retries, self.backoff = timeout, retries, backoff
        self.allowlist = ALLOWLIST if allowlist is None else allowlist
        self._tools: dict[str, Any] | None = None

    async def _load(self) -> dict[str, Any]:
        if self._tools is None:
            for attempt in range(self.retries + 1):
                try:
                    tools = await asyncio.wait_for(self.client.get_tools(), self.timeout)
                    if len({t.name for t in tools}) != len(tools):
                        raise ToolCallError('Duplicate MCP tool name; server ownership is ambiguous')
                    self._tools = {t.name: t for t in tools}
                    break
                except Exception as error:
                    if isinstance(error, ToolCallError):
                        raise
                    if not transport_error(error):
                        raise ToolCallError('MCP discovery rejected or misconfigured; check server authentication and schemas') from error
                    if attempt == self.retries:
                        raise McpUnavailable(f'MCP discovery unavailable after {attempt + 1} attempts') from error
                    await asyncio.sleep(self.backoff * 2**attempt)
        return self._tools

    async def tool_names_for(self, agent: str) -> set[str]:
        return set(await self._load()) & self.allowlist.get(agent, set())

    async def call(self, agent: str, tool: str, args: dict[str, Any]) -> Any:
        if tool not in self.allowlist.get(agent, set()):
            raise PermissionError(f"agent {agent!r} may not call tool {tool!r}")
        proposal = args.get('proposal') if isinstance(args.get('proposal'), dict) else {}
        preview = tool == 'create_proposal_draft' and proposal.get('dry_run') is True
        if agent == 'approval_preview' and not preview:
            raise PermissionError('approval_preview may only request dry_run=true')
        if tool in MUTATING:
            key = proposal.get('idempotency_key') if tool == 'create_proposal_draft' else args.get('idempotency_key')
            if not isinstance(key, str) or not 8 <= len(key) <= 64:
                raise PermissionError('Every MCP write/preview requires a valid idempotency key')
        tools = await self._load()
        if tool not in tools:
            raise ToolCallError(f'Tool {tool!r} was not advertised by the configured server')
        attempts = self.retries + 1 if tool not in MUTATING or preview else 1
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                raw = await asyncio.wait_for(tools[tool].ainvoke(args), self.timeout)
                return json.loads(raw[0]["text"]) if isinstance(raw, list) else raw
            except ToolException as e:
                raise ToolCallError(str(e)) from e
            except Exception as error:
                if not transport_error(error):
                    raise ToolCallError(f'MCP {tool} failed without a retryable transport error') from error
                last = error
                if attempt + 1 < attempts:
                    await asyncio.sleep(self.backoff * 2**attempt)
        self._tools = None
        raise McpUnavailable(f"{tool} unavailable after {attempts} attempts") from last


def mcp_search_fn(tools: AgentTools, agent: str = "fit_matcher"):
    """Adapt search_evidence to the async SearchFn the RAG variants expect."""
    async def search(query: str, k: int, filters: dict | None = None) -> list[dict]:
        res = await tools.call(agent, "search_evidence", {"requirement": query, "k": k,
                                                         "filters": filters or None})
        return res["items"]
    return search
