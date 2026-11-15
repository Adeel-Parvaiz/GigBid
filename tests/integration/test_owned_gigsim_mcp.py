import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import httpx

from agent.config import load_config
from agent.marketplace_mcp import build_mcp_port
from tests.conftest import free_port


async def test_owned_gigsim_through_real_mcp(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    rest_port, mcp_port = free_port(), free_port()
    env = {**os.environ, 'GIGBID_DATA_DIR': str(root / 'data/sample'), 'GIGSIM_DB': str(tmp_path / 'sim.sqlite'),
           'GIGSIM_TOKENS_JSON': json.dumps({'test-rest-token': 'alice'}), 'GIGSIM_API_TOKEN': 'test-rest-token',
           'GIGSIM_API_URL': f'http://127.0.0.1:{rest_port}', 'GIGSIM_CONTRACT': str(root / 'config/gigsim_contract.json'),
           'MARKETPLACE_MODE': 'gigsim', 'MARKETPLACE_MCP_TOKENS': 'test-mcp-token:alice',
           'MARKETPLACE_AUDIT': str(tmp_path / 'audit.jsonl'), 'PORT': str(mcp_port), 'MARKETPLACE_RPM': '1000'}
    commands = [[sys.executable, '-m', 'uvicorn', 'apps.gigsim.main:create_app', '--factory', '--port', str(rest_port)],
                [sys.executable, '-m', 'mcp_servers.marketplace.server']]
    processes = [subprocess.Popen(c, cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for c in commands]
    try:
        for number in [rest_port, mcp_port]:
            for _ in range(100):
                try:
                    socket.create_connection(('127.0.0.1', number), timeout=.1).close()
                    break
                except OSError:
                    await asyncio.sleep(.1)
            else:
                raise AssertionError('GigSim/MCP startup failed')
        monkeypatch.setenv('MARKETPLACE_MCP_TOKEN', 'test-mcp-token')
        port = build_mcp_port(load_config(overrides={'marketplace': {'url': f'http://127.0.0.1:{mcp_port}/mcp'}}))
        job = (await port.search_jobs('churn'))[0]
        assert (await port.get_job(job['job_id']))['job_id'] == job['job_id']
        assert (await port.get_client_history(job['client_id']))['client_id'] == job['client_id']
        payload = {'job_id': job['job_id'], 'cover_letter': 'Python churn analysis with a reproducible baseline.', 'bid_amount': 100}
        await port.create_proposal_draft(payload, 'owned-preview', True)
        assert (await port.get_connects_balance())['balance'] == 100
        draft = await port.create_proposal_draft(payload, 'owned-proposal')
        await port.submit_proposal(draft['draft_id'], 'owned-submit')
        await port.submit_proposal(draft['draft_id'], 'owned-submit-new')
        assert (await port.get_connects_balance())['balance'] == 100 - job['connects_cost']
        thread = (await port.list_threads())[0]['thread_id']
        await port.send_message(thread, 'A simulated response.', 'owned-message')
        await port.send_message(thread, 'A simulated response.', 'owned-message')
        messages = await port.list_messages(thread)
        assert sum(m['text'] == 'A simulated response.' for m in messages['messages']) == 1
        async with httpx.AsyncClient() as client:
            outcomes = (await client.get(f'http://127.0.0.1:{rest_port}/v1/outcomes',
                                         headers={'Authorization': 'Bearer test-rest-token'})).json()['outcomes']
        assert len(outcomes) == 1 and outcomes[0]['source'] == 'synthetic-rule-based-client'
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(10)
