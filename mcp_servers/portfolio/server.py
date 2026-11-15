"""Portfolio MCP server (read-only). Run: python -m mcp_servers.portfolio.server [stdio|streamable-http]"""
from __future__ import annotations

import os
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from apps.api.auth.oauth_store import OAuthVault
from mcp_servers.portfolio import prompts, resources
from mcp_servers.portfolio.identity import PortfolioIdentityMiddleware, portfolio_identity
from mcp_servers.portfolio.tools import (
    EvidenceItem,
    PortfolioStore,
    SearchEvidenceResult,
    SearchFilters,
    SkillList,
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def build_server(store: PortfolioStore | None = None, descriptions: dict[str, str] | None = None) -> FastMCP:
    stores: dict[tuple[str, str | None], PortfolioStore] = {}

    def get_store() -> PortfolioStore:
        if store is not None:
            return store
        identity = portfolio_identity.get()
        if identity is None:
            user_id = os.environ.get("PORTFOLIO_USER_ID")
            freelancer_id = os.environ.get("PORTFOLIO_FREELANCER_ID")
        else:
            user_id, freelancer_id = identity
        if not user_id:
            return PortfolioStore()
        key = (user_id, freelancer_id)
        if key not in stores:
            vault = OAuthVault(
                database=os.environ.get("OAUTH_DB"),
                key=os.environ.get("OAUTH_ENCRYPTION_KEY"),
            )
            stores[key] = PortfolioStore(user_id=user_id, freelancer_id=freelancer_id, vault=vault)
        return stores[key]

    descriptions = descriptions or {}
    mcp = FastMCP(
        "gigbid-portfolio",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8765")),
        transport_security=TransportSecuritySettings(
            allowed_hosts=["portfolio-mcp:*", "127.0.0.1:*", "localhost:*"]
        ),
    )

    @mcp.tool(annotations=READ_ONLY, description=descriptions.get("search_evidence", (
        "Search the freelancer's portfolio for proof of ONE requirement (a skill, tool or deliverable). "
        "Returns evidence items with type, source, date and outcome. Call once per requirement.")))
    def search_evidence(requirement: str, k: int = 5, filters: SearchFilters | None = None) -> SearchEvidenceResult:
        if not 2 <= len(requirement) <= 100_000:
            raise ValueError("requirement must be 2-100000 characters")
        if not 1 <= k <= 20:
            raise ValueError("k must be between 1 and 20")
        return get_store().search_evidence(requirement, k, filters)

    @mcp.tool(annotations=READ_ONLY, description=descriptions.get(
        "get_case_study", "Fetch one portfolio item (case study or past proposal) by evidence_id."))
    def get_case_study(id: str) -> EvidenceItem:
        return get_store().get_case_study(id)

    @mcp.tool(annotations=READ_ONLY, description=descriptions.get(
        "list_skills", "List every skill in the portfolio with how many items mention it."))
    def list_skills() -> SkillList:
        return get_store().list_skills()

    resources.register(mcp, get_store)
    prompts.register(mcp)
    return mcp


def main() -> None:
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    server = build_server()
    if transport == "streamable-http":
        import uvicorn

        app = server.streamable_http_app()
        app.add_middleware(
            PortfolioIdentityMiddleware,
            token=os.environ.get("PORTFOLIO_MCP_TOKEN", ""),
        )
        uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8765")))
        return
    server.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
