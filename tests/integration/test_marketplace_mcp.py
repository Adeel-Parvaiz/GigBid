import json

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from agent.graphs.bid_graph import build_bid_graph
from agent.marketplace_mcp import McpMarketplacePort
from agent.marketplace_port import MarketplaceError
from agent.mcp_client import AgentTools
from agent.tracing import current_trace_id
from tests.conftest import cfg_of


def port_for(srv, token="tok-alice", **kw):
    conn = {"transport": "streamable_http", "url": srv["url"], "headers": {"Authorization": f"Bearer {token}"}}
    return McpMarketplacePort(AgentTools({"marketplace": conn}, **kw))


def audit_rows(srv):
    return [json.loads(line) for line in srv["audit"].read_text().splitlines()]


async def test_http_endpoint_requires_bearer_token(market_server):
    for hdr in ({}, {"Authorization": "Bearer wrong"}):
        r = httpx.post(market_server["url"], headers=hdr, json={})
        assert r.status_code == 401


async def test_tool_annotations_and_constraints(market_server):
    async with streamablehttp_client(market_server["url"], headers={"Authorization": "Bearer tok-alice"}) as (r, w, _):
        async with ClientSession(r, w) as c:
            await c.initialize()
            tools = {t.name: t for t in (await c.list_tools()).tools}
    assert len(tools) == 9
    for name in ("search_jobs", "get_job", "get_client_history", "get_connects_balance", "list_messages", "list_threads"):
        assert tools[name].annotations.readOnlyHint is True
    assert tools["create_proposal_draft"].annotations.destructiveHint is False
    for name in ("submit_proposal", "send_message"):
        a = tools[name].annotations
        assert a.destructiveHint is True and a.idempotentHint is True and a.readOnlyHint is False
        assert "idempotency_key" in tools[name].inputSchema["required"]
    schema = json.dumps(tools["create_proposal_draft"].inputSchema)
    assert '"maxLength": 5000' in schema and '"exclusiveMinimum": 0' in schema and "idempotency_key" in schema


async def test_dry_run_creates_nothing_and_bad_input_is_rejected(market_server):
    p = port_for(market_server)
    payload = {"job_id": "job-001", "cover_letter": "Hi", "screening_answers": [], "bid_amount": 300, "currency": "USD"}
    dry = await p.create_proposal_draft(payload, "key-dry-run-1", dry_run=True)
    assert dry["dry_run"] is True and dry["connects_cost"] == 8 and dry["draft_id"] is None
    assert (await p.get_connects_balance())["balance"] == 100
    with pytest.raises(MarketplaceError):
        await p.create_proposal_draft({**payload, "bid_amount": -5}, "key-bad-input-1")
    with pytest.raises(MarketplaceError):
        await p.create_proposal_draft({**payload, "cover_letter": ""}, "key-bad-input-2")
    with pytest.raises(MarketplaceError):
        await p.get_job("../etc/passwd")


async def test_submit_is_idempotent_and_insufficient_connects_is_typed(market_server):
    p = port_for(market_server)
    payload = {"job_id": "job-001", "cover_letter": "Hello", "screening_answers": [], "bid_amount": 300, "currency": "USD"}
    d = await p.create_proposal_draft(payload, "key-idem-0001")
    a = await p.submit_proposal(d["draft_id"], "key-idem-0001")
    b = await p.submit_proposal(d["draft_id"], "key-idem-0001")        # a retry
    assert a["replayed"] is False and b["replayed"] is True
    assert (await p.get_connects_balance())["balance"] == 92
    with pytest.raises(MarketplaceError) as e:
        await p.submit_proposal("draft-9999", "key-other-0001")
    assert e.value.code == "draft_not_found"


async def test_bid_graph_over_marketplace_mcp_and_audit_log(market_server, make_deps, profile):
    current_trace_id.set("trace-abc123")
    deps = make_deps(port=port_for(market_server))
    g = build_bid_graph(deps, InMemorySaver())
    await g.ainvoke({"job_id": "job-001", "profile": profile}, cfg_of("t-mm"))
    out = await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("t-mm"))
    assert out["status"] == "submitted" and out["submission"]["connects_spent"] == 8
    rows = audit_rows(market_server)
    assert {"get_job", "get_client_history", "create_proposal_draft", "submit_proposal"} <= {r["tool"] for r in rows}
    assert all(r["user"] == "alice" and r["trace_id"] == "trace-abc123" for r in rows)
    # the dry-run preview happened before approval, the real submit only after
    tools = [r["tool"] for r in rows]
    assert tools.index("submit_proposal") > max(i for i, r in enumerate(rows) if r["args"].get("dry_run") is True)


async def test_audit_log_masks_pii_and_scopes_user(market_server):
    p = port_for(market_server, token="tok-bob")
    await p.send_message("conv-001", "Reach me at jane@example.com or +92 300 1234567", "key-send-0001")
    row = [r for r in audit_rows(market_server) if r["tool"] == "send_message"][0]
    assert row["user"] == "bob" and "jane@example.com" not in json.dumps(row) and "1234567" not in json.dumps(row)


async def test_server_down_is_marketplace_unavailable_and_graph_reports_error(make_deps, profile):
    dead = port_for({"url": "http://127.0.0.1:9/mcp"}, timeout=2, retries=0)
    g = build_bid_graph(make_deps(port=dead), InMemorySaver())
    out = await g.ainvoke({"job_id": "job-001", "profile": profile}, cfg_of("t-down"))
    assert out["status"] == "error" and "marketplace_unavailable" in out["errors"][0]
