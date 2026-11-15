from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.workspace.server import build_server


async def test_slots_holds_and_drafts():
    async with connect(build_server()) as c:
        s = (await c.call_tool("get_free_slots", {"start_date": "2026-11-09", "limit": 3})).structuredContent["slots"]
        assert len(s) == 3 and not any(x["start"].endswith("10:00") for x in s)
        h1 = (await c.call_tool("create_tentative_hold", {"start": s[0]["start"], "title": "Interview", "idempotency_key": "hold-key-0001"})).structuredContent
        h2 = (await c.call_tool("create_tentative_hold", {"start": s[0]["start"], "title": "Interview", "idempotency_key": "hold-key-0001"})).structuredContent
        assert h1["hold_id"] == h2["hold_id"] and h2["replayed"] is True
        again = (await c.call_tool("get_free_slots", {"start_date": "2026-11-09", "limit": 3})).structuredContent["slots"]
        assert s[0]["start"] not in {x["start"] for x in again}                     # held slot is no longer free
        clash = await c.call_tool("create_tentative_hold", {"start": s[0]["start"], "title": "x", "idempotency_key": "hold-key-0002"})
        assert clash.isError
        e = (await c.call_tool("create_email_draft", {"to": "a@b.co", "subject": "Hi", "body": "Hello", "idempotency_key": "mail-key-0001"})).structuredContent
        assert e["status"] == "draft"
        bad = await c.call_tool("get_free_slots", {"start_date": "tomorrow"})
        assert bad.isError


async def test_annotations_never_destructive():
    async with connect(build_server()) as c:
        for t in (await c.list_tools()).tools:
            assert t.annotations.destructiveHint is False and t.annotations.idempotentHint is True
