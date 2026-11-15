from datetime import date, timedelta

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.config import load_config
from agent.graphs.conversation_graph import build_conversation_graph
from agent.mcp_client import AgentTools, ToolCallError, workspace_connection
from agent.runtime import build_deps
from agent.workspace_mcp import McpWorkspace
from tests.conftest import cfg_of


def monday():
    today = date.today()
    return (today + timedelta(days=(7 - today.weekday()) % 7)).isoformat()


def test_application_rejects_direct_workspace_configuration():
    with pytest.raises(ValueError, match='requires MCP'):
        build_deps(load_config(overrides={'workspace': {'source': 'local'}}))


async def test_all_workspace_tools_use_mcp_and_persist_across_processes(tmp_path, monkeypatch):
    monkeypatch.setenv('WORKSPACE_DB', str(tmp_path / 'workspace.sqlite'))
    cfg = load_config()
    assert cfg['workspace']['source'] == 'mcp'
    tools = AgentTools({'workspace': workspace_connection(cfg)})
    workspace = McpWorkspace(tools)
    slots = await workspace.get_free_slots(monday(), 5, 30, 3)
    assert (tmp_path / 'workspace.sqlite').is_file(), 'stdio child must use the configured server-side state'
    assert len(slots.slots) == 3
    start = slots.slots[0].start
    hold = await workspace.create_tentative_hold(start, 'Interview', 'workspace-hold')
    assert hold.status == 'tentative'
    email = await workspace.create_email_draft('client@example.com', 'Interview', 'Please confirm the tentative interview.', 'workspace-email')
    assert email.status == 'draft'
    # MultiServerMCPClient starts a fresh stdio process for each call. Recreate the entire client too.
    restored = McpWorkspace(AgentTools({'workspace': workspace_connection(cfg)}))
    assert (await restored.create_tentative_hold(start, 'Interview', 'workspace-hold')).replayed
    assert (await restored.create_email_draft('client@example.com', 'Interview', 'Please confirm the tentative interview.', 'workspace-email')).replayed
    assert start not in [s.start for s in (await restored.get_free_slots(monday())).slots]
    with pytest.raises(ToolCallError, match='idempotency_conflict'):
        await restored.create_email_draft('client@example.com', 'Changed', 'Different content.', 'workspace-email')
    with pytest.raises(PermissionError):
        await tools.call('liaison_calendar', 'create_email_draft', {})


async def test_default_application_conversation_holds_only_after_approval(tmp_path, monkeypatch, profile):
    monkeypatch.setenv('WORKSPACE_DB', str(tmp_path / 'approval.sqlite'))
    cfg = load_config(overrides={'conversation': {'start_date': monday()}})
    deps = build_deps(cfg)
    assert isinstance(deps.workspace, McpWorkspace)
    graph = build_conversation_graph(deps, InMemorySaver())
    config = cfg_of('workspace-default-application')
    await graph.ainvoke({'thread_id': 'conv-002', 'profile': profile}, config)
    snapshot = await graph.aget_state(config)
    pending = next(i.value for t in snapshot.tasks for i in t.interrupts)
    start = pending['offered_slots'][0]
    assert start in [s.start for s in (await deps.workspace.get_free_slots(monday())).slots]
    out = await graph.ainvoke(Command(resume={'action': 'approve'}), config)
    assert out['send_result']['hold']['status'] == 'tentative'
    assert start not in [s.start for s in (await deps.workspace.get_free_slots(monday())).slots]
