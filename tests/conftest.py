import asyncio
import os
import socket
import subprocess
import sys
import time

import pytest

from agent.config import load_config
from agent.runtime import build_deps, load_sample_profile


@pytest.hookimpl(optionalhook=True)
def pytest_asyncio_loop_factories(config, item):
    if os.name != "nt":
        return {"default": asyncio.new_event_loop}
    # Psycopg's async connections require a selector loop on Windows.
    if item.path.name == "test_postgres_durability.py":
        return {"postgres_selector": asyncio.SelectorEventLoop}
    return {"windows_default": asyncio.ProactorEventLoop}


@pytest.fixture
def profile():
    return load_sample_profile()


@pytest.fixture
def make_deps():
    def _make(overrides=None, **kw):
        cfg = load_config(overrides=overrides)
        if not (overrides or {}).get('workspace', {}).get('source') == 'mcp':
            from mcp_servers.workspace.tools import WorkspaceService
            kw.setdefault('workspace', WorkspaceService())
        return build_deps(cfg, **kw)
    return _make


def cfg_of(thread: str):
    return {"configurable": {"thread_id": thread}}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def market_server(tmp_path):
    """A real Marketplace MCP server (HTTP + bearer auth) in a subprocess; fresh state per test."""
    port, audit = free_port(), tmp_path / "audit.jsonl"
    env = {**os.environ, "PORT": str(port), "MARKETPLACE_MCP_TOKENS": "tok-alice:alice,tok-bob:bob",
           "MARKETPLACE_AUDIT": str(audit), "MARKETPLACE_RPM": "1000"}
    p = subprocess.Popen([sys.executable, "-m", "mcp_servers.marketplace.server"], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield {"url": f"http://127.0.0.1:{port}/mcp", "audit": audit, "port": port}
    p.terminate()
    p.wait(5)
