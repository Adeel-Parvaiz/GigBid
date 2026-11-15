"""One real-LLM drafting agent, MCP-only data access, disposable project-owned GigSim."""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agent.config import load_config
from agent.marketplace_mcp import build_mcp_port
from evals.runners.verify_owned_gigsim import free_port
from mcp_servers.portfolio.server import build_server
from mcp_servers.portfolio.tools import PortfolioStore

ROOT = Path(__file__).resolve().parents[2]


async def drafting_agent(marketplace, portfolio, model_client):
    """The agent accesses job, balance, evidence and draft preview exclusively through MCP."""
    job = await marketplace.get_job('job-001')
    before = await marketplace.get_connects_balance()
    evidence = await portfolio.call_tool('search_evidence', {'requirement': 'customer churn Python classification', 'k': 3})
    assert not evidence.isError
    items = evidence.structuredContent['items']
    result = await model_client.post('http://127.0.0.1:11435/v1/chat/completions', json={
        'model': 'qwen25-15b', 'temperature': 0, 'seed': 4016, 'max_tokens': 500,
        'response_format': {'type': 'json_object'}, 'messages': [
            {'role': 'system', 'content': (ROOT / 'agent/prompts/grounded_single_agent.md').read_text()},
            {'role': 'user', 'content': '<data>' + json.dumps({'job': job, 'evidence': items}) + '</data>'}]})
    result.raise_for_status()
    response = result.json()
    draft = json.loads(response['choices'][0]['message']['content'])
    assert len(draft['plan']) == 3 and all(s.startswith('I will') for s in draft['plan'])
    plan = ' '.join(draft['plan']).lower()
    assert all(term in plan for term in ['logistic regression', 'random forest', 'precision', 'recall', 'limitations'])
    assert 1 <= len(draft['evidence_ids']) <= 3
    assert not re.search(r'\b(guarantee|previous|years|achieved)\b|\d+%', ' '.join(draft['plan']), re.I)
    sources = {item['evidence_id']: item for item in items}
    cited = [sources[eid] for eid in dict.fromkeys(draft['evidence_ids'])]
    # Verify against full items fetched over MCP, rather than accepting model-authored claims.
    for item in cited:
        full = await portfolio.call_tool('get_case_study', {'id': item['evidence_id']})
        assert not full.isError and full.structuredContent['summary'] == item['summary']
    text = f'Proposal: {job["title"]}\n\n' + '\n'.join(draft['plan']) + '\n\nRelevant portfolio evidence:\n'
    for item in cited:
        text += f'\n[{item["evidence_id"]}] "{item["summary"]}"\nSource: {item["source"]}; date: {item.get("date")}; type: {item["type"]}.\n'
    payload = {'job_id': job['job_id'], 'cover_letter': text, 'bid_amount': 300, 'currency': 'USD',
               'screening_answers': []}
    preview = await marketplace.create_proposal_draft(payload, 'single-grounded-preview', dry_run=True)
    after = await marketplace.get_connects_balance()
    assert before == after and preview['dry_run']
    return {'model': 'qwen25-15b', 'job': job, 'proposal': text, 'selected_evidence': cited,
            'model_draft': draft, 'raw_response': response['choices'][0]['message']['content'],
            'usage': response['usage'], 'preview': preview, 'balance_before': before, 'balance_after': after,
            'checks': {'mcp_only_data_access': True, 'one_llm_agent': True, 'exact_evidence_quotes': True,
                       'all_citations_fetched_and_verified': True, 'dry_run_only': True, 'zero_connects_spent': True},
            'limitations': 'Synthetic sample job and portfolio, project-owned GigSim. Plan requires human review; no submission or actual hiring result.'}


async def run():
    rest, mcp = free_port(), free_port()
    with tempfile.TemporaryDirectory(prefix='gigbid-single-agent-') as temp:
        env = {**os.environ, 'GIGBID_DATA_DIR': str(ROOT / 'data/sample'), 'GIGSIM_DB': f'{temp}/sim.sqlite',
               'GIGSIM_TOKENS_JSON': json.dumps({'single-rest': 'single-agent'}), 'GIGSIM_API_TOKEN': 'single-rest',
               'GIGSIM_API_URL': f'http://127.0.0.1:{rest}', 'GIGSIM_CONTRACT': str(ROOT / 'config/gigsim_contract.json'),
               'MARKETPLACE_MODE': 'gigsim', 'MARKETPLACE_MCP_TOKENS': 'single-mcp:single-agent',
               'MARKETPLACE_AUDIT': f'{temp}/audit.jsonl', 'MARKETPLACE_RPM': '1000', 'PORT': str(mcp)}
        children = []
        try:
            for command in [[sys.executable, '-m', 'uvicorn', 'apps.gigsim.main:create_app', '--factory', '--host', '127.0.0.1', '--port', str(rest)],
                            [sys.executable, '-m', 'mcp_servers.marketplace.server']]:
                children.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            async with httpx.AsyncClient(timeout=150) as client:
                for url in [f'http://127.0.0.1:{rest}/health', f'http://127.0.0.1:{mcp}/mcp']:
                    for _ in range(100):
                        try:
                            await client.get(url)
                            break
                        except httpx.TransportError:
                            await asyncio.sleep(.1)
                    else:
                        raise RuntimeError('Disposable fixture startup failed')
                os.environ['MARKETPLACE_MCP_TOKEN'] = 'single-mcp'
                cfg = load_config(overrides={'marketplace': {'mode': 'mcp', 'url': f'http://127.0.0.1:{mcp}/mcp'}})
                async with connect(build_server(PortfolioStore(ROOT / 'data/sample', freelancer_id='sample-ai-engineer'))) as portfolio:
                    report = await drafting_agent(build_mcp_port(cfg), portfolio, client)
            report['created_at'] = datetime.now(UTC).isoformat()
            report['marketplace'] = 'project-owned GigSim REST through authenticated Marketplace MCP'
            output = ROOT / 'evals/results/single_grounded_proposal.json'
            output.write_text(json.dumps(report, indent=2))
            output.with_suffix('.md').write_text('# Single-agent grounded GigSim proposal\n\nSynthetic assignment fixture evidence; not real client work.\n\n' + report['proposal'])
            print(json.dumps(report['checks']))
        finally:
            for child in children:
                child.terminate()
            for child in children:
                child.wait(10)


if __name__ == '__main__':
    asyncio.run(run())
