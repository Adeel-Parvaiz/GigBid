"""Portfolio MCP server (read-only). Run: python -m mcp_servers.portfolio.server [stdio|streamable-http]"""
from __future__ import annotations

import os
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_servers.portfolio import prompts, resources
from mcp_servers.portfolio.tools import (
    EvidenceItem,
    PortfolioStore,
    SearchEvidenceResult,
    SearchFilters,
    SkillList,
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def build_server(store: PortfolioStore | None = None, descriptions: dict[str, str] | None = None) -> FastMCP:
    store = store or PortfolioStore()
    descriptions = descriptions or {}
    mcp = FastMCP("gigbid-portfolio", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8765")))

    @mcp.tool(annotations=READ_ONLY, description=descriptions.get("search_evidence", (
        "Search the freelancer's portfolio for proof of ONE requirement (a skill, tool or deliverable). "
        "Returns evidence items with type, source, date and outcome. Call once per requirement.")))
    def search_evidence(requirement: str, k: int = 5, filters: SearchFilters | None = None) -> SearchEvidenceResult:
        if not 2 <= len(requirement) <= 100_000:
            raise ValueError("requirement must be 2-100000 characters")
        if not 1 <= k <= 20:
            raise ValueError("k must be between 1 and 20")
        return store.search_evidence(requirement, k, filters)

    @mcp.tool(annotations=READ_ONLY, description=descriptions.get(
        "get_case_study", "Fetch one portfolio item (case study or past proposal) by evidence_id."))
    def get_case_study(id: str) -> EvidenceItem:
        return store.get_case_study(id)

    @mcp.tool(annotations=READ_ONLY, description=descriptions.get(
        "list_skills", "List every skill in the portfolio with how many items mention it."))
    def list_skills() -> SkillList:
        return store.list_skills()

    resources.register(mcp, store)
    prompts.register(mcp)
    return mcp


def main() -> None:
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    build_server().run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
