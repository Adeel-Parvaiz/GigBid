"""Real stdio subprocess: the bid graph gets its evidence ONLY through the Portfolio MCP server."""
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph, pending_approval
from agent.mcp_client import AgentTools, McpUnavailable, ToolCallError, portfolio_connection
from tests.conftest import cfg_of


def tools(**kw):
    return AgentTools({"portfolio": portfolio_connection(load_config())}, **kw)


async def test_allowlist_is_enforced_per_agent():
    t = tools()
    assert await t.tool_names_for("fit_matcher") == {"search_evidence"}
    assert await t.tool_names_for("critic") == {"search_evidence"}
    assert await t.tool_names_for("writer") == {"search_evidence", "get_case_study"}
    with pytest.raises(PermissionError):
        await t.call("fit_matcher", "list_skills", {})
    with pytest.raises(PermissionError):
        await t.call("unknown_agent", "search_evidence", {"requirement": "python"})


async def test_tool_errors_raise_instead_of_looking_like_evidence():
    with pytest.raises(ToolCallError):
        await tools().call("fit_matcher", "search_evidence", {"requirement": "x"})


async def test_unreachable_server_is_degraded_mode_signal():
    t = AgentTools({"portfolio": {"transport": "stdio", "command": "/nonexistent/binary", "args": []}},
                   timeout=3, retries=0)
    with pytest.raises(McpUnavailable):
        await t.call("fit_matcher", "search_evidence", {"requirement": "python"})


async def test_bid_graph_runs_end_to_end_through_mcp(make_deps, profile):
    deps = make_deps({"portfolio": {"source": "mcp"}})
    g = build_bid_graph(deps, InMemorySaver())
    out = await g.ainvoke({"job_id": "job-001", "profile": profile}, cfg_of("t-mcp"))
    assert out["fit_report"].score >= 0.6 and out["evidence"]
    p = await pending_approval(g, cfg_of("t-mcp"))
    assert p and all(c["evidence_ids"] for c in p["draft"]["claims"] if c["kind"] == "claim")
    assert deps.port.submissions == {}
