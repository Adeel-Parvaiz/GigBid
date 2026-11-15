import os
import socket
import subprocess
import sys
import time

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.config import load_config
from agent.graphs.conversation_graph import build_conversation_graph
from tests.conftest import cfg_of, free_port


async def test_conversation_graph_uses_workspace_only_through_mcp(make_deps, profile, tmp_path):
    port = free_port()
    p = subprocess.Popen([sys.executable, "-m", "mcp_servers.workspace.server", "streamable-http"],
                         env={**os.environ, "PORT": str(port), "WORKSPACE_DB": str(tmp_path / 'workspace.sqlite')}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        deps = make_deps({"workspace": {"source": "mcp", "transport": "streamable_http", "url": f"http://127.0.0.1:{port}/mcp"}})
        g = build_conversation_graph(deps, InMemorySaver())
        await g.ainvoke({"thread_id": "conv-002", "profile": profile}, cfg_of("w"))
        pend = [i.value for t in (await g.aget_state(cfg_of("w"))).tasks for i in t.interrupts][0]
        assert len(pend["offered_slots"]) == 3
        out = await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("w"))
        assert out["send_result"]["hold"]["status"] == "tentative"
        # the hold really exists in the MCP server: asking for the same slot again is now taken
        from agent.nodes.liaison import calendar_start_date

        again = await deps.workspace.get_free_slots(calendar_start_date(load_config()["conversation"]), 5, 30, 3)
        assert pend["offered_slots"][0] not in [s.start for s in again.slots]
    finally:
        p.terminate()
        p.wait(10)


def test_env_overrides_parse_nested_yaml_values():
    from agent.config import env_overrides
    assert env_overrides({"GIGBID__portfolio__source": "mcp", "GIGBID__budgets__max_revisions": "3", "OTHER": "x"}) == \
        {"portfolio": {"source": "mcp"}, "budgets": {"max_revisions": 3}}
