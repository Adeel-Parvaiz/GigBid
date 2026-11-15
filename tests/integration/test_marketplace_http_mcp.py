import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import httpx

from agent.config import load_config
from agent.marketplace_mcp import build_mcp_port
from tests.conftest import free_port


async def test_contract_rest_adapter_works_through_authenticated_real_mcp(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    upstream_port, mcp_port = free_port(), free_port()
    env = {**os.environ, "GIGBID_DATA_DIR": str(root / "data/sample"), "MARKETPLACE_MODE": "gigsim",
           "GIGSIM_API_URL": f"http://127.0.0.1:{upstream_port}", "GIGSIM_CONTRACT": str(root / "tests/fixtures/marketplace_http_contract.json"),
           "GIGSIM_API_TOKEN": "fixture-upstream", "MARKETPLACE_MCP_TOKENS": "fixture-mcp:alice",
           "MARKETPLACE_AUDIT": str(tmp_path / "audit.jsonl"), "PORT": str(mcp_port), "MARKETPLACE_RPM": "1000"}
    commands = [[sys.executable, "-m", "uvicorn", "tests.fixtures.marketplace_http_app:create_app", "--factory", "--port", str(upstream_port)],
                [sys.executable, "-m", "mcp_servers.marketplace.server"]]
    processes = [subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for command in commands]
    try:
        for port in [upstream_port, mcp_port]:
            for _ in range(100):
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=.1).close()
                    break
                except OSError:
                    await asyncio.sleep(.1)
            else:
                raise AssertionError("Local HTTP/MCP fixture did not start")
        monkeypatch.setenv("MARKETPLACE_MCP_TOKEN", "fixture-mcp")
        port = build_mcp_port(load_config(overrides={"marketplace": {"url": f"http://127.0.0.1:{mcp_port}/mcp"}}))
        jobs = await port.search_jobs("churn")
        job = await port.get_job(jobs[0]["job_id"])
        assert (await port.get_client_history(job["client_id"]))["client_id"] == job["client_id"]
        assert (await port.get_connects_balance())["balance"] == 100
        payload = {"job_id": job["job_id"], "freelancer_id": "sample-ai-engineer", "cover_letter": "A fixture proposal.", "screening_answers": [], "bid_amount": 300, "currency": "USD"}
        await port.create_proposal_draft(payload, "fixture-proposal-key", True)
        async with httpx.AsyncClient(headers={"Authorization": "Bearer fixture-upstream"}) as client:
            url = f"http://127.0.0.1:{upstream_port}/fixture/counters"
            assert (await client.get(url)).json() == {"balance": 100, "drafts": 0, "submissions": 0, "sent": 0}
            draft = await port.create_proposal_draft(payload, "fixture-proposal-key")
            await port.submit_proposal(draft["draft_id"], "fixture-proposal-key")
            await port.submit_proposal(draft["draft_id"], "fixture-proposal-key")
            threads = await port.list_threads()
            await port.list_messages(threads[0]["thread_id"])
            await port.send_message(threads[0]["thread_id"], "Fixture reply.", "fixture-message-key")
            await port.send_message(threads[0]["thread_id"], "Fixture reply.", "fixture-message-key")
            counts = (await client.get(url)).json()
            assert counts == {"balance": 100 - job["connects_cost"], "drafts": 1, "submissions": 1, "sent": 1}
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(10)
