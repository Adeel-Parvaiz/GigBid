"""B3 real-model drafts, before/after verification, and clearly separate synthetic stress cases."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agent.config import load_config
from agent.deps import Deps
from agent.handoffs import Claim, ProposalDraft
from agent.llm import OpenAICompatLLM
from agent.nodes import critic, verifier, writer
from mcp_servers.marketplace.adapters.sample import SampleAdapter
from mcp_servers.marketplace.server import build_server as market_server
from mcp_servers.marketplace.tools import MarketplaceService
from mcp_servers.portfolio.server import build_server as portfolio_server
from mcp_servers.portfolio.tools import PortfolioStore
from rag.verify import configured_verdicts

ROOT = Path(__file__).resolve().parents[2]


def summarize(rows):
    before = sum(r['stats']['claims_total'] for r in rows)
    after = sum(r['stats']['claims_after'] for r in rows)
    bad_before = sum(r['stats']['unsupported_before'] for r in rows)
    bad_after = sum(r['post_verdicts_unsupported'] for r in rows)
    return {'proposals': len(rows), 'claims_before': before, 'claims_after': after,
            'unsupported_before': bad_before, 'unsupported_after_rechecked': bad_after,
            'unsupported_rate_before': bad_before / before if before else None,
            'unsupported_rate_after': bad_after / after if after else None,
            'retained_claim_fraction': after / before if before else None,
            'unsupported_per_proposal_before': bad_before / len(rows) if rows else 0,
            'unsupported_per_proposal_after': bad_after / len(rows) if rows else 0,
            'partly_supported_before': sum(r['stats']['partly_supported_before'] for r in rows),
            'empty_clean_drafts': sum(not r['clean']['claims'] for r in rows)}


async def run():
    load_dotenv(ROOT / '.env')
    cfg = load_config(overrides={'verification': {'backend': 'llm'}})
    usage, stage = [], {'name': ''}
    async def measure(response):
        await response.aread()
        if response.is_success:
            data = response.json()
            usage.append({'stage': stage['name'], 'model': data.get('model'), 'usage': data.get('usage'),
                          'response': data.get('choices', [{}])[0].get('message', {}).get('content')})
    output = ROOT / 'evals/results/b3'
    output.mkdir(parents=True, exist_ok=True)
    data = ROOT / 'data/processed/kaggle_2024_v1'
    import tempfile
    with tempfile.TemporaryDirectory(prefix='gigbid-b3-') as temp:
        async with httpx.AsyncClient(timeout=150, event_hooks={'response': [measure]}) as client:
            llm = OpenAICompatLLM(cfg, client)
            if not llm.base_url.startswith(('http://127.0.0.1:', 'http://localhost:')):
                raise ValueError('This evaluation requires the already configured local model')
            deps = Deps(None, None, llm, cfg)
            rows = []
            async with connect(market_server(MarketplaceService(SampleAdapter(data), Path(temp) / 'audit.jsonl', per_minute=1000))) as marketplace:
                for persona in ['ai-ml-engineer', 'fullstack-dev', 'data-analyst']:
                    cases = json.loads((ROOT / f'evals/datasets/kaggle_2024_v1/dev_{persona}.json').read_text())['jobs']
                    selected = [c for c in cases if c['gold_action'] == 'bid' and c['job_id'].startswith('syn-')][:4]
                    async with connect(portfolio_server(PortfolioStore(data, freelancer_id=persona))) as portfolio:
                        for case in selected:
                            stage['name'] = f'{persona}/{case["job_id"]}/writer'
                            job = (await marketplace.call_tool('get_job', {'job_id': case['job_id']})).structuredContent
                            result = await portfolio.call_tool('search_evidence', {
                                'requirement': ' '.join(job['required_skills']), 'k': 5, 'filters': {'freelancer_id': persona, 'retrieval_layer': 'hybrid'}})
                            evidence = result.structuredContent['items']
                            state = {'job': job, 'job_spec': {**job, 'screening_questions': job.get('screening_questions', [])},
                                     'fit_report': {'evidence_ids': [e['evidence_id'] for e in evidence]}, 'evidence': evidence, 'profile': {'freelancer_id': persona}}
                            start = time.perf_counter()
                            original = (await writer.make(deps)(state))['proposal_draft']
                            state['proposal_draft'] = original
                            stage['name'] = f'{persona}/{case["job_id"]}/verification'
                            verified = await verifier.make(deps)(state)
                            state.update(verified)
                            clean = ProposalDraft.model_validate(verified['proposal_draft'])
                            stage['name'] = f'{persona}/{case["job_id"]}/repeat-check'
                            post = await configured_verdicts(clean.claims, evidence, llm, cfg['verification'])
                            stage['name'] = f'{persona}/{case["job_id"]}/critic-after-verification'
                            critique = await critic.make(deps)(state)
                            row = {'persona': persona, 'job_id': job['job_id'], 'evidence': evidence, 'original': original,
                                   'clean': verified['proposal_draft'], 'verdicts_before': verified['claim_verification'],
                                   'stats': verified['verification_stats'], 'verdicts_after_repeat': [v.model_dump() for v in post],
                                   'post_verdicts_unsupported': sum(v.label == 'unsupported' for v in post),
                                   'critic_input_was_cleaned': True, 'critique': critique['critique'],
                                   'seconds': time.perf_counter() - start}
                            rows.append(row)
                            (output / 'proposals.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
                            print(persona, job['job_id'], row['stats']['unsupported_before'], '->', row['post_verdicts_unsupported'], flush=True)
            # Deliberately injected controls, never mixed with naturally generated draft rates.
            ev = [{'evidence_id': 'control', 'title': 'Classification baseline', 'skills': ['Python'],
                   'summary': 'Built a Python classification baseline in 2019.', 'outcome': ''}]
            controls = [
                ('exact supported fact', 'Built a Python classification baseline in 2019.', ['control'], 'supported'),
                ('fabricated number', 'Built a Python classification baseline for 99 banks.', ['control'], 'unsupported'),
                ('unknown citation', 'Built a Python classification baseline.', ['missing'], 'unsupported'),
                ('substring number', 'Built a Python classification baseline in 19.', ['control'], 'unsupported'),
                ('invented employer', 'Built a Python classification baseline at Google.', ['control'], 'unsupported'),
                ('unsupported extra action', 'Built a Python classification baseline and deployed it globally.', ['control'], 'partly_supported')]
            stress = []
            for name, text, ids, expected in controls:
                stage['name'] = 'synthetic-control/' + name
                original = ProposalDraft(job_id='control', claims=[Claim(text=text, evidence_ids=ids, kind='boilerplate')])
                verified = await verifier.make(deps)({'proposal_draft': original.model_dump(mode='json'), 'evidence': ev})
                actual = verified['claim_verification'][0]['label']
                stress.append({'name': name, 'expected_synthetic_label': expected, 'actual': actual,
                               'correct': expected == actual, **verified})
            report = {'created_at': datetime.now(UTC).isoformat(), 'backend': 'real OpenAICompatLLM semantic check plus deterministic guards',
                      'models': llm.models, 'endpoint': llm.base_url, 'all': summarize(rows),
                      'per_persona': {p: summarize([r for r in rows if r['persona'] == p]) for p in ['ai-ml-engineer', 'fullstack-dev', 'data-analyst']},
                      'synthetic_controls': stress, 'usage': usage,
                      'limits': 'Synthetic evidence/gold; 12 natural real-model drafts. Controls are deliberately injected and separately reported. Semantic checker is not human-calibrated and repeat checking is not independent human ground truth. No proposals submitted.'}
            (output / 'summary.json').write_text(json.dumps(report, indent=2))
            print(json.dumps(report['all'], indent=2))


if __name__ == '__main__':
    asyncio.run(run())
