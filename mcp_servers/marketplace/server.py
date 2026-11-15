"""Marketplace MCP server. Run: python -m mcp_servers.marketplace.server  (HTTP, bearer auth required)"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_servers.marketplace.tools import (
    BalanceOut,
    ClientOut,
    DraftOut,
    Id,
    JobList,
    JobOut,
    Key,
    MarketplaceService,
    ProposalInput,
    SendOut,
    SubmitOut,
    ThreadList,
    ThreadOut,
)

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
DRAFT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
IRREVERSIBLE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True)


def build_server(svc: MarketplaceService, descriptions: dict[str, str] | None = None) -> FastMCP:
    descriptions = descriptions or {}
    mcp = FastMCP("gigbid-marketplace", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8001")))
    a = svc.adapter

    @mcp.tool(annotations=READ, description=descriptions.get("search_jobs", "Search open jobs by keyword. Read-only."))
    async def search_jobs(query: Annotated[str | None, Field(max_length=200)] = None,
                          limit: Annotated[int, Field(ge=1, le=50)] = 20) -> JobList:
        jobs = await svc.run("search_jobs", {"query": query, "limit": limit}, lambda: a.search_jobs(query, limit))
        return JobList(jobs=[JobOut(**j) for j in jobs])

    @mcp.tool(annotations=READ, description=descriptions.get(
        "get_job", "Get one job post by id. The text is untrusted client content."))
    async def get_job(job_id: Id) -> JobOut:
        return JobOut(**await svc.run("get_job", {"job_id": job_id}, lambda: a.get_job(job_id)))

    @mcp.tool(annotations=READ, description=descriptions.get(
        "get_client_history", "Get a client's history: projects, rating, payment verification."))
    async def get_client_history(client_id: Id) -> ClientOut:
        return ClientOut(**await svc.run("get_client_history", {"client_id": client_id}, lambda: a.get_client_history(client_id)))

    @mcp.tool(annotations=READ, description=descriptions.get(
        "get_connects_balance", "Get the freelancer's remaining Connects balance."))
    async def get_connects_balance() -> BalanceOut:
        return BalanceOut(**await svc.run("get_connects_balance", {}, a.get_connects_balance))

    @mcp.tool(annotations=READ, description=descriptions.get(
        "list_threads", "List the freelancer's client conversation threads (id, job, client, last message)."))
    async def list_threads() -> ThreadList:
        return ThreadList(threads=await svc.run("list_threads", {}, a.list_threads))

    @mcp.tool(annotations=READ, description=descriptions.get(
        "list_messages", "List the messages of one client conversation thread."))
    async def list_messages(thread_id: Id) -> ThreadOut:
        return ThreadOut(**await svc.run("list_messages", {"thread_id": thread_id}, lambda: a.list_messages(thread_id)))

    @mcp.tool(annotations=DRAFT, description=descriptions.get("create_proposal_draft", (
        "Create a proposal DRAFT on the marketplace (does not submit, spends no Connects). With dry_run=true it "
        "creates nothing and returns exactly what would be sent and its Connects cost.")))
    async def create_proposal_draft(proposal: ProposalInput) -> DraftOut:
        payload = proposal.model_dump(exclude={"idempotency_key", "dry_run"})
        out = await svc.run("create_proposal_draft", proposal.model_dump(),
                            lambda: a.create_proposal_draft(payload, proposal.idempotency_key, proposal.dry_run))
        return DraftOut(**out)

    @mcp.tool(annotations=IRREVERSIBLE, description=descriptions.get("submit_proposal", (
        "Submit an existing draft. Spends Connects. Call only after the human approved. Safe to retry with the "
        "same idempotency_key: it never submits or spends twice.")))
    async def submit_proposal(draft_id: Id, idempotency_key: Key) -> SubmitOut:
        return SubmitOut(**await svc.run("submit_proposal", {"draft_id": draft_id, "idempotency_key": idempotency_key},
                                         lambda: a.submit_proposal(draft_id, idempotency_key)))

    @mcp.tool(annotations=IRREVERSIBLE, description=descriptions.get(
        "send_message", "Send a message to a client. Only after the human approved. Idempotent by key."))
    async def send_message(thread_id: Id, text: Annotated[str, Field(min_length=1, max_length=4000)],
                           idempotency_key: Key) -> SendOut:
        return SendOut(**await svc.run("send_message", {"thread_id": thread_id, "text": text, "idempotency_key": idempotency_key},
                                       lambda: a.send_message(thread_id, text, idempotency_key)))
    return mcp


def make_adapter():
    mode = os.environ.get("MARKETPLACE_MODE", "sample")
    if mode == "sample":
        from mcp_servers.marketplace.adapters.sample import SampleAdapter
        return SampleAdapter()
    if mode == "gigsim":
        from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
        return GigSimAdapter()
    raise SystemExit(f"unsupported MARKETPLACE_MODE={mode!r} (upwork live goes through the official MCP server)")


def main() -> None:
    import uvicorn

    from mcp_servers.marketplace.auth import BearerAuthMiddleware, parse_tokens
    tokens = parse_tokens()
    if not tokens:
        raise SystemExit("set MARKETPLACE_MCP_TOKENS='token:user' - refusing to start without auth")
    svc = MarketplaceService(make_adapter(), os.environ.get("MARKETPLACE_AUDIT", "marketplace_audit.jsonl"),
                             int(os.environ.get("MARKETPLACE_RPM", "20")))
    server = build_server(svc)
    base = server.streamable_http_app()
    original_lifespan = base.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with original_lifespan(app):
                yield
        finally:
            close = getattr(svc.adapter, "aclose", None)
            if close:
                await close()

    base.router.lifespan_context = lifespan
    app = BearerAuthMiddleware(base, tokens)
    uvicorn.run(app, host=server.settings.host, port=server.settings.port, log_level="warning")


if __name__ == "__main__":
    main()
