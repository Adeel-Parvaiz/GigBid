"""Exercise the real local LLM and bid graph against our disposable GigSim over MCP."""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.llm import OpenAICompatLLM, build_llm
from agent.marketplace_mcp import build_mcp_port
from agent.runtime import build_deps, load_sample_profile


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


async def run():
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / '.env', override=False)
    data = root / 'data/processed/kaggle_2024_v1'
    rest, mcp = free_port(), free_port()
    rows = []
    with tempfile.TemporaryDirectory(prefix='gigbid-owned-sim-') as temp:
        env = {**os.environ, 'GIGBID_DATA_DIR': str(data), 'GIGSIM_DB': f'{temp}/sim.sqlite',
               'GIGSIM_TOKENS_JSON': json.dumps({'evaluation-rest': 'evaluator'}), 'GIGSIM_API_TOKEN': 'evaluation-rest',
               'GIGSIM_API_URL': f'http://127.0.0.1:{rest}', 'GIGSIM_CONTRACT': str(root / 'config/gigsim_contract.json'),
               'MARKETPLACE_MODE': 'gigsim', 'MARKETPLACE_MCP_TOKENS': 'evaluation-mcp:evaluator',
               'MARKETPLACE_AUDIT': f'{temp}/audit.jsonl', 'MARKETPLACE_RPM': '1000', 'PORT': str(mcp)}
        commands = [[sys.executable, '-m', 'uvicorn', 'apps.gigsim.main:create_app', '--factory', '--port', str(rest)],
                    [sys.executable, '-m', 'mcp_servers.marketplace.server']]
        processes = [subprocess.Popen(c, cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for c in commands]
        try:
            for port_number in [rest, mcp]:
                for _ in range(100):
                    try:
                        socket.create_connection(('127.0.0.1', port_number), timeout=.1).close()
                        break
                    except OSError:
                        await asyncio.sleep(.1)
                else:
                    raise RuntimeError('GigSim/MCP startup failed')
            os.environ['MARKETPLACE_MCP_TOKEN'] = 'evaluation-mcp'
            cfg = load_config(overrides={'marketplace': {'mode': 'mcp', 'url': f'http://127.0.0.1:{mcp}/mcp'}})
            llm = build_llm(cfg)
            if not isinstance(llm, OpenAICompatLLM):
                raise RuntimeError('This verifier requires a real configured model; heuristic execution refused')
            for persona in ['ai-ml-engineer', 'fullstack-dev', 'data-analyst']:
                cases = json.loads((root / f'evals/datasets/kaggle_2024_v1/dev_{persona}.json').read_text())['jobs']
                case = next(c for c in cases if c['gold_action'] == 'bid')
                if persona == 'ai-ml-engineer':
                    # A previously verified ordinary job; other personas retain their first gold-bid case.
                    case = {'job_id': 'syn-101281', 'gold_action': 'bid'}
                port = build_mcp_port(cfg)
                deps = build_deps(cfg, port=port, llm=llm, data_dir=data)
                graph = build_bid_graph(deps, InMemorySaver())
                config = {'configurable': {'thread_id': f'owned-sim-{persona}'}}
                row = {'persona': persona, 'job_id': case['job_id'], 'gold_action': case['gold_action']}
                start = time.perf_counter()
                try:
                    before = (await port.get_connects_balance())['balance']
                    state = await asyncio.wait_for(graph.ainvoke({'job_id': case['job_id'], 'profile': load_sample_profile(persona, data)}, config), 180)
                    snap = await graph.aget_state(config)
                    pending = next((i.value for t in snap.tasks for i in t.interrupts), None)
                    row.update({'decision': state.get('decision'), 'status_before': state.get('status'),
                                'approval_gate_reached': pending is not None, 'trace': state.get('trace', []),
                                'preview_spent_zero_connects': (await port.get_connects_balance())['balance'] == before,
                                'blocking_reasons': pending.get('blocking_reasons', []) if pending else []})
                    if pending and 'approve' in pending['allowed_actions']:
                        final = await graph.ainvoke(Command(resume={'action': 'approve'}), config)
                        row['status_after_sandbox_approval'] = final.get('status')
                        row['connects_spent'] = before - (await port.get_connects_balance())['balance']
                    else:
                        row['sandbox_submission'] = 'not attempted: skipped or blocked by normal gate'
                except Exception as error:
                    row['error'] = f'{type(error).__name__}: {error}'
                row['seconds'] = round(time.perf_counter() - start, 3)
                rows.append(row)
                print(json.dumps(row), flush=True)
            async with httpx.AsyncClient() as client:
                outcomes = (await client.get(f'http://127.0.0.1:{rest}/v1/outcomes', headers={'Authorization': 'Bearer evaluation-rest'})).json()
            report = {'scope': 'Real local LLM + actual bid graph + authenticated MCP + project-owned GigSim REST + disposable SQLite',
                      'llm': cfg['llm']['profiles'][cfg['llm']['profile']]['nodes'],
                      'approval': 'Scripted approvals only inside disposable synthetic simulator; not human evaluation or real marketplace writes.',
                      'cases': rows, 'outcomes': outcomes}
            (root / 'evals/results/owned_gigsim_real_agent.json').write_text(json.dumps(report, indent=2))
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                process.wait(10)


if __name__ == '__main__':
    asyncio.run(run())
