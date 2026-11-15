"""Resumable full-development real-agent B4 evaluation against isolated GigSim/MCP."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.marketplace_context import marketplace_user
from agent.marketplace_mcp import build_mcp_port
from agent.runtime import build_deps, load_sample_profile
from evals.rd_b.b4_services import marketplace_env, match_outcome
from evals.runners.open_model_comparison import MeasuredLLM

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'evals/results/b4'
STATE = ROOT / '.local-models/b4-evaluation-v2'
PROTOCOL = Path(__file__).with_name('b4_protocol.json')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def ordered_cases(protocol, per_persona_limit=None):
    per_persona = {}
    for index, persona in enumerate(protocol['personas']):
        cases = json.loads((ROOT / f'evals/datasets/kaggle_2024_v1/dev_{persona}.json').read_text())['jobs']
        cases = sorted(cases, key=lambda c: (c['gold_action'] != 'bid', not c['job_id'].startswith('syn-'), c['job_id']))
        if per_persona_limit is not None:
            if not 1 <= per_persona_limit <= len(cases):
                raise ValueError(f'per-persona limit must be between 1 and {len(cases)}')
            cases = random.Random(protocol['evaluation_seed'] + index).sample(cases, per_persona_limit)
        per_persona[persona] = cases
    return [(persona, case) for i in range(max(map(len, per_persona.values())))
            for persona in protocol['personas'] for case in per_persona[persona][i:i + 1]]


def resolve_path(value, default):
    path = Path(value) if value else Path(default)
    return path if path.is_absolute() else ROOT / path


async def run(args):
    load_dotenv(ROOT / '.env')
    protocol = json.loads(PROTOCOL.read_text())
    output_dir = resolve_path(getattr(args, 'results_dir', None), 'evals/results/b4')
    state_dir = resolve_path(getattr(args, 'state_dir', None), '.local-models/b4-evaluation-v2')
    output_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    per_persona_limit = getattr(args, 'per_persona_limit', None)
    cases = ordered_cases(protocol, per_persona_limit)
    if args.limit:
        if per_persona_limit is not None:
            raise ValueError('Use either --limit or --per-persona-limit, not both')
        cases = cases[:args.limit]
    manifest = {'protocol': protocol, 'protocol_sha256': hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
                'planned_case_pairs': len(cases), 'planned_graph_runs': len(cases) * 2,
                'hashes': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in [ROOT / 'data/processed/kaggle_2024_v1/portfolio_items.json',
                                        *sorted((ROOT / 'evals/datasets/kaggle_2024_v1').glob('dev_*.json'))]}}
    if per_persona_limit is not None:
        manifest['sample_mode'] = 'exploratory_random_per_persona'
        manifest['per_persona_limit'] = per_persona_limit
        manifest['sampling_seed'] = protocol['evaluation_seed']
    existing = output_dir / 'manifest.json'
    if existing.exists() and json.loads(existing.read_text()) != manifest:
        raise ValueError('Evaluation manifest changed; use a separate output directory rather than mixing cohorts')
    existing.write_text(json.dumps(manifest, indent=2))
    result_path = output_dir / 'runs.jsonl'
    previous = [json.loads(line) for line in result_path.read_text().splitlines()] if result_path.exists() else []
    done = {(r['persona'], r['job_id'], r['variant']) for r in previous}
    rest = free_port()
    mcps = {v: free_port() for v in protocol['variants']}
    portfolio_port = free_port()
    data = ROOT / 'data/processed/kaggle_2024_v1'
    tokens = {'b4-rest-' + v: 'b4-' + v for v in protocol['variants']}
    env = {**os.environ, 'GIGBID_DATA_DIR': str(data), 'PORTFOLIO_DIR': str(data),
           'GIGSIM_DB': str(state_dir / 'gigsim.sqlite'), 'GIGSIM_CONNECTS': '1000000',
           'GIGSIM_TOKENS_JSON': json.dumps(tokens), 'GIGSIM_API_TOKEN': 'b4-rest-v0_naive',
           'GIGSIM_API_URL': f'http://127.0.0.1:{rest}', 'GIGSIM_CONTRACT': str(ROOT / 'config/gigsim_contract.json'),
           'MARKETPLACE_MODE': 'gigsim', 'MARKETPLACE_MCP_TOKENS': 'b4-mcp-v0_naive:b4-v0_naive,b4-mcp-v8_corrective:b4-v8_corrective',
           'MARKETPLACE_AUDIT': str(state_dir / 'audit.jsonl'), 'MARKETPLACE_RPM': '100000'}
    portfolio_rag = {'embedder': 'fastembed', 'fastembed_model': 'sentence-transformers/all-MiniLM-L6-v2',
                     'fastembed_batch_size': 32, 'cache_dir': str(ROOT / '.local-models/rag-cache'),
                     'model_threads': 2, 'chunk_size': 1200, 'chunk_overlap': 150,
                     'reranker': 'fastembed', 'reranker_model': 'Xenova/ms-marco-MiniLM-L-6-v2'}
    portfolio_env = {**env, 'PORT': str(portfolio_port), 'PORTFOLIO_RAG_CONFIG': json.dumps(portfolio_rag)}
    children = []
    try:
        with (state_dir / 'services.log').open('a') as log:
            command = [sys.executable, '-m', 'uvicorn', 'apps.gigsim.main:create_app', '--factory', '--host', '127.0.0.1', '--port', str(rest)]
            children.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log))
            for variant, port in mcps.items():
                children.append(subprocess.Popen([sys.executable, '-m', 'mcp_servers.marketplace.server'],
                    cwd=ROOT, env=marketplace_env(env, variant, port), stdout=log, stderr=log))
            children.append(subprocess.Popen([sys.executable, '-m', 'mcp_servers.portfolio.server', 'streamable-http'],
                cwd=ROOT, env=portfolio_env, stdout=log, stderr=log))
            async with httpx.AsyncClient(timeout=10) as client:
                urls = [f'http://127.0.0.1:{rest}/health', *[f'http://127.0.0.1:{p}/mcp' for p in mcps.values()],
                        f'http://127.0.0.1:{portfolio_port}/mcp']
                for url in urls:
                    attempts = 1800 if 'portfolio' in url else 100
                    for _ in range(attempts):
                        try:
                            await client.get(url)
                            break
                        except httpx.TransportError:
                            await asyncio.sleep(.1)
                    else:
                        raise RuntimeError('Isolated evaluation service startup failed')
            os.environ['PORTFOLIO_DIR'] = str(data)
            os.environ['WORKSPACE_DB'] = str(state_dir / 'workspace.sqlite')
            for persona, case in cases:
                for variant in protocol['variants']:
                    if (persona, case['job_id'], variant) in done:
                        continue
                    os.environ['MARKETPLACE_MCP_TOKEN'] = 'b4-mcp-' + variant
                    cfg = load_config(overrides={'rag': {'variant': variant, 'embedder': 'fastembed', 'reranker': 'fastembed',
                                                        'cache_dir': str(ROOT / '.local-models/rag-cache')},
                        'portfolio': {'source': 'mcp', 'transport': 'streamable_http',
                                      'url': f'http://127.0.0.1:{portfolio_port}/mcp'},
                        'workspace': {'source': 'mcp', 'transport': 'stdio'},
                        'marketplace': {'mode': 'mcp', 'url': f'http://127.0.0.1:{mcps[variant]}/mcp'}, 'verification': {'backend': 'auto'}})
                    llm = MeasuredLLM(cfg)
                    if not llm.base_url.startswith(('http://localhost:', 'http://127.0.0.1:')):
                        raise ValueError('This evaluation may use only the configured local model endpoint')
                    port = build_mcp_port(cfg)
                    deps = build_deps(cfg, port=port, llm=llm, data_dir=data)
                    graph = build_bid_graph(deps, InMemorySaver())
                    thread = {'configurable': {'thread_id': f'b4-{variant}-{persona}-{case["job_id"]}'}}
                    row = {'persona': persona, 'job_id': case['job_id'], 'variant': variant, 'gold': case,
                           'error': None, 'outcome': None, 'submitted': False, 'scope': 'isolated synthetic GigSim only'}
                    start = time.perf_counter()
                    context = marketplace_user.set('b4-' + variant)
                    try:
                        state = await asyncio.wait_for(graph.ainvoke({'job_id': case['job_id'],
                            'profile': load_sample_profile(persona, data)}, thread), 240)
                        analysis_seconds = time.perf_counter() - start
                        snapshot = await graph.aget_state(thread)
                        pending = next((i.value for task in snapshot.tasks for i in task.interrupts), None)
                        row.update({'analysis_seconds': analysis_seconds, 'decision': state.get('decision'),
                                    'job': state.get('job'), 'risk': state.get('risk_report'), 'price': state.get('price_quote'),
                                    'evidence': state.get('evidence', []), 'proposal': state.get('proposal_draft'),
                                    'verification': state.get('verification_stats'), 'claim_verdicts': state.get('claim_verification'),
                                    'trace': state.get('trace', []), 'critique': state.get('critique'), 'status': state.get('status'),
                                    'approval_allowed': bool(pending and 'approve' in pending['allowed_actions']),
                                    'blocking_reasons': pending.get('blocking_reasons', []) if pending else state.get('errors', [])})
                        if pending and 'approve' in pending['allowed_actions']:
                            final = await asyncio.wait_for(graph.ainvoke(Command(resume={'action': 'approve'}), thread), 60)
                            row['submitted'] = final.get('status') == 'submitted'
                            row['submission'] = final.get('submission')
                            async with httpx.AsyncClient(timeout=20) as client:
                                result = await client.get(f'http://127.0.0.1:{rest}/v1/outcomes', headers={
                                    'Authorization': 'Bearer b4-rest-' + variant})
                                result.raise_for_status()
                                outcomes = result.json()['outcomes']
                                row['outcome'] = match_outcome(outcomes, row.get('submission')) if row['submitted'] else None
                                row['outcome_match'] = 'draft_id'
                    except Exception as error:
                        row['error'] = f'{type(error).__name__}: {str(error)[:400]}'
                        row['analysis_seconds'] = time.perf_counter() - start
                    finally:
                        marketplace_user.reset(context)
                        await llm.client.aclose()
                    row['total_seconds'] = time.perf_counter() - start
                    row['calls'] = llm.calls
                    row['tokens'] = sum((c.get('prompt_tokens') or 0) + (c.get('completion_tokens') or 0) for c in llm.calls)
                    row['tokens_complete'] = all(c.get('prompt_tokens') is not None and c.get('completion_tokens') is not None for c in llm.calls)
                    row['billed_api_usd'] = 0
                    row['hardware_cost_usd'] = None
                    with result_path.open('a') as output:
                        output.write(json.dumps(row) + '\n')
                    done.add((persona, case['job_id'], variant))
                    print(len(done), '/', len(cases) * 2, persona, variant, case['job_id'],
                          (row.get('decision') or {}).get('action'), row['submitted'], row['error'], flush=True)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            child.wait(15)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, help='Diagnostic only; written manifest distinguishes it from the full run')
    parser.add_argument('--per-persona-limit', type=int, help='Deterministic random exploratory sample size per persona')
    parser.add_argument('--results-dir', help='Result directory; defaults to evals/results/b4')
    parser.add_argument('--state-dir', help='Isolated simulator/service state directory')
    asyncio.run(run(parser.parse_args()))
