from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.marketplace.adapters.sample import SampleAdapter
from mcp_servers.marketplace.server import build_server
from mcp_servers.marketplace.tools import MarketplaceService


async def test_rate_limit_per_user_with_fake_clock(tmp_path):
    now = [0.0]
    svc = MarketplaceService(SampleAdapter(), tmp_path / "a.jsonl", per_minute=2, clock=lambda: now[0])
    async with connect(build_server(svc)) as c:
        assert not (await c.call_tool("get_connects_balance", {})).isError
        assert not (await c.call_tool("get_connects_balance", {})).isError
        r = await c.call_tool("get_connects_balance", {})
        assert r.isError and "rate_limited" in r.content[0].text
        now[0] = 61.0                                             # window passes
        assert not (await c.call_tool("get_connects_balance", {})).isError
    outcomes = [line for line in (tmp_path / "a.jsonl").read_text().splitlines()]
    assert any("rate_limited" in o for o in outcomes)
