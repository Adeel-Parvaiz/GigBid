from __future__ import annotations

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from mcp_servers.portfolio.tools import PortfolioStore


def register(mcp: FastMCP, get_store: Callable[[], PortfolioStore]) -> None:
    @mcp.resource("portfolio://case/{case_id}", mime_type="application/json",
                  description="Full case study as JSON.")
    def case(case_id: str) -> str:
        return get_store().get_case_study(case_id).model_dump_json(indent=1)

    @mcp.resource("portfolio://proposal/{proposal_id}", mime_type="application/json",
                  description="A past proposal with its outcome (won / replied / ignored).")
    def proposal(proposal_id: str) -> str:
        store = get_store()
        it = store._visible(proposal_id, store.bound)
        if it["type"] != "past_proposal":
            raise ValueError(f"{proposal_id!r} is not a past proposal")
        return store.get_case_study(proposal_id).model_dump_json(indent=1)
