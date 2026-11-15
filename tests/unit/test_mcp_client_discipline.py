import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from langchain_core.tools import ToolException

from agent.mcp_client import ALLOWLIST, AgentTools, McpUnavailable, ToolCallError


def tools(name, effect):
    client = AgentTools({}, timeout=.02, retries=2, backoff=0)
    tool = SimpleNamespace(name=name, ainvoke=AsyncMock(side_effect=effect))
    client._tools = {name: tool}
    return client, tool


async def test_every_role_denies_tools_outside_its_allowlist_before_network():
    client = AgentTools({})
    client._load = AsyncMock()
    names = set().union(*ALLOWLIST.values())
    for role, allowed in ALLOWLIST.items():
        for name in names - allowed:
            with pytest.raises(PermissionError):
                await client.call(role, name, {})
    client._load.assert_not_awaited()
    empty = AgentTools({}, allowlist={})
    with pytest.raises(PermissionError):
        await empty.call('scout', 'search_jobs', {})


async def test_preview_role_cannot_create_a_real_draft():
    client = AgentTools({})
    client._load = AsyncMock()
    with pytest.raises(PermissionError, match='dry_run'):
        await client.call('approval_preview', 'create_proposal_draft', {'proposal': {'dry_run': False, 'idempotency_key': 'preview-key'}})
    client._load.assert_not_awaited()


async def test_nested_transport_errors_retry_and_tool_errors_do_not():
    wrapped = ExceptionGroup('transport', [ExceptionGroup('nested', [httpx.ConnectError('offline')])])
    client, tool = tools('get_job', [wrapped, {'job_id': 'job-1'}])
    assert await client.call('load_job', 'get_job', {'job_id': 'job-1'}) == {'job_id': 'job-1'}
    assert tool.ainvoke.await_count == 2
    client, tool = tools('get_job', ToolException('job_not_found'))
    with pytest.raises(ToolCallError, match='job_not_found'):
        await client.call('load_job', 'get_job', {'job_id': 'job-1'})
    assert tool.ainvoke.await_count == 1


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_http_rate_limits_and_server_errors_are_retried(status):
    failure = httpx.HTTPStatusError(
        "temporary marketplace failure",
        request=httpx.Request("GET", "http://fixture/mcp"),
        response=httpx.Response(status),
    )
    client, tool = tools("get_job", [failure, {"job_id": "job-1"}])
    assert await client.call("load_job", "get_job", {"job_id": "job-1"}) == {"job_id": "job-1"}
    assert tool.ainvoke.await_count == 2


async def test_discovery_backoff_is_bounded_and_auth_failure_is_not_retried(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr('agent.mcp_client.asyncio.sleep', sleep)
    client = AgentTools({}, retries=2, backoff=.1)
    client.client.get_tools = AsyncMock(side_effect=httpx.ConnectError('offline'))
    with pytest.raises(McpUnavailable, match='3 attempts'):
        await client._load()
    assert client.client.get_tools.await_count == 3
    assert [call.args[0] for call in sleep.await_args_list] == [.1, .2]
    client.client.get_tools = AsyncMock(side_effect=httpx.HTTPStatusError('unauthorized', request=httpx.Request('GET', 'http://fixture/mcp'), response=httpx.Response(401)))
    with pytest.raises(ToolCallError):
        await client._load()
    assert client.client.get_tools.await_count == 1


async def test_rpc_timeout_and_mutating_no_retry():
    async def delayed(_):
        await asyncio.sleep(1)
    client, tool = tools('get_job', delayed)
    with pytest.raises(McpUnavailable, match='3 attempts'):
        await asyncio.wait_for(client.call('load_job', 'get_job', {'job_id': 'job-1'}), .5)
    assert tool.ainvoke.await_count == 3
    client, tool = tools('send_message', httpx.ReadError('uncertain after send'))
    with pytest.raises(McpUnavailable, match='1 attempts'):
        await client.call('approval_gate', 'send_message', {'thread_id': 'thread-1', 'text': 'Approved.', 'idempotency_key': 'approved-key'})
    assert tool.ainvoke.await_count == 1


async def test_duplicate_tool_names_are_rejected():
    client = AgentTools({})
    client.client.get_tools = AsyncMock(return_value=[SimpleNamespace(name='ambiguous'), SimpleNamespace(name='ambiguous')])
    with pytest.raises(ToolCallError, match='Duplicate'):
        await client._load()
