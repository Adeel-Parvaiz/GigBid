"""Fails CI when a tool signature changes unintentionally (A7).
Descriptions are deliberately NOT snapshotted: R&D question A rewrites them on purpose.
Intentional change? Re-run with UPDATE_SNAPSHOTS=1 and commit the diff."""
import json
import os
import sys
from pathlib import Path

from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.portfolio.server import build_server

SNAP = Path(__file__).parent / "snapshots"


async def signatures(server) -> dict:
    async with connect(server) as c:
        tools = (await c.list_tools()).tools
    return {t.name: {"input": t.inputSchema, "output": t.outputSchema,
                     "annotations": t.annotations.model_dump(exclude_none=True) if t.annotations else None}
            for t in sorted(tools, key=lambda t: t.name)}


async def check(name: str, server):
    got, path = await signatures(server), SNAP / f"{name}.json"
    if os.environ.get("UPDATE_SNAPSHOTS"):
        assert not os.environ.get('CI'), 'Snapshot updates are forbidden in CI; review and update locally'
        path.write_text(json.dumps(got, indent=1, sort_keys=True))
    assert path.exists(), f'Missing committed {name} snapshot; generate intentionally with UPDATE_SNAPSHOTS=1'
    assert got == json.loads(path.read_text()), f"{name} tool signatures changed; see {path}"


async def test_portfolio_signatures_are_stable():
    await check("portfolio", build_server())


async def test_workspace_signatures_are_stable():
    from mcp_servers.workspace.server import build_server as workspace_server
    from mcp_servers.workspace.tools import WorkspaceService
    await check('workspace', workspace_server(WorkspaceService()))


async def test_marketplace_signatures_are_stable(tmp_path):
    from mcp_servers.marketplace.adapters.sample import SampleAdapter
    from mcp_servers.marketplace.server import build_server as marketplace_server
    from mcp_servers.marketplace.tools import MarketplaceService
    data = Path(__file__).resolve().parents[2] / 'data/sample'
    await check('marketplace', marketplace_server(MarketplaceService(SampleAdapter(data), tmp_path / 'audit.jsonl')))


async def test_snapshot_gate_detects_signature_drift(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(sys.modules[__name__], 'SNAP', tmp_path)
    monkeypatch.delenv('UPDATE_SNAPSHOTS', raising=False)
    got = await signatures(build_server())
    got['search_evidence']['input']['properties']['requirement']['type'] = 'integer'
    (tmp_path / 'drift.json').write_text(json.dumps(got))
    with pytest.raises(AssertionError, match='signatures changed'):
        await check('drift', build_server())


async def test_snapshot_gate_refuses_missing_baselines_and_ci_updates(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(sys.modules[__name__], 'SNAP', tmp_path)
    monkeypatch.delenv('UPDATE_SNAPSHOTS', raising=False)
    with pytest.raises(AssertionError, match='Missing committed'):
        await check('absent', build_server())
    monkeypatch.setenv('UPDATE_SNAPSHOTS', '1')
    monkeypatch.setenv('CI', 'true')
    with pytest.raises(AssertionError, match='forbidden in CI'):
        await check('forbidden', build_server())
    assert not (tmp_path / 'forbidden.json').exists()
