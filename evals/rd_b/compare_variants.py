"""B2 one-command comparison: fixed chunks, real embeddings and real cross-encoder."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from agent.config import load_config
from agent.nodes.fit_matcher import requirements_of
from evals.metrics import mrr, ndcg_at_k, recall_at_k
from rag.index.vector import DenseIndex
from rag.retriever import RetrievalQuery, build_retriever, make_embedder, make_reranker
from rag.variants.v0_naive import chunk_items

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ('v0_naive', 'v1_decomposed', 'v2_hybrid', 'v3_rerank', 'v8_corrective')


async def run(args):
    output = ROOT / 'evals/results/b2'
    output.mkdir(parents=True, exist_ok=True)
    cfg = load_config(overrides={'rag': {'embedder': args.embedder, 'reranker': args.reranker,
                                        'cache_dir': str(ROOT / '.local-models/rag-cache')}})
    items = json.loads((args.data / 'portfolio_items.json').read_text())
    chunks = chunk_items(items, cfg['rag']['chunk_size'], cfg['rag']['chunk_overlap'])
    embedder, reranker = make_embedder(cfg), make_reranker(cfg)
    index = DenseIndex(chunks, embedder)
    jobs = {j['job_id']: j for j in json.loads((args.data / 'jobs.json').read_text())}
    dev = {p: json.loads((args.dev / f'dev_{p}.json').read_text())['jobs']
           for p in ('ai-ml-engineer', 'fullstack-dev', 'data-analyst')}
    rows = []
    for variant in VARIANTS:
        retriever = build_retriever({**cfg, 'rag': {**cfg['rag'], 'variant': variant}}, items,
                                    embedder=embedder, reranker=reranker, dense_index=index)
        for persona, cases in dev.items():
            for case in cases:
                job = jobs[case['job_id']]
                query = RetrievalQuery(f"{job['title']}. {job['description']}", requirements_of(job), {'freelancer_id': persona})
                start = time.perf_counter()
                hits = await retriever.retrieve(query, 10)
                elapsed = (time.perf_counter() - start) * 1000
                # Gold labels identify source evidence items, not newly derived chunk IDs.
                ranked = list(dict.fromkeys(h.get('parent_evidence_id', h['evidence_id']) for h in hits))
                gold = set(case['gold_evidence'])
                rows.append({'variant': variant, 'persona': persona, 'job_id': case['job_id'],
                             'retrieved_chunk_ids': [h['evidence_id'] for h in hits], 'ranked_source_ids': ranked,
                             'gold': sorted(gold), 'refused': not hits, 'latency_ms': elapsed,
                             'recall@5': recall_at_k(ranked, gold, 5) if gold else None,
                             'mrr': mrr(ranked, gold) if gold else None,
                             'ndcg@10': ndcg_at_k(ranked, gold, 10) if gold else None})
        (output / 'trials.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        print(variant, 'completed', flush=True)
    groups = defaultdict(list)
    for row in rows:
        groups[row['variant'], row['persona']].append(row)
        groups[row['variant'], 'all'].append(row)
    scores = []
    for (variant, persona), group in groups.items():
        relevant = [r for r in group if r['gold']]
        scores.append({'variant': variant, 'persona': persona, 'jobs': len(group), 'relevance_jobs': len(relevant),
                       **{metric: float(np.mean([r[metric] for r in relevant])) for metric in ('recall@5', 'mrr', 'ndcg@10')},
                       'p50_ms': float(np.percentile([r['latency_ms'] for r in group], 50)),
                       'p95_ms': float(np.percentile([r['latency_ms'] for r in group], 95)),
                       'refused': sum(r['refused'] for r in group)})
    report = {'created_at': datetime.now(UTC).isoformat(), 'trials': len(rows), 'source_items': len(items), 'chunks': len(chunks),
              'chunk_size': cfg['rag']['chunk_size'], 'chunk_overlap': cfg['rag']['chunk_overlap'],
              'embedding': getattr(embedder, 'metadata', {'model': args.embedder}),
              'reranker': getattr(reranker, 'metadata', {'model': args.reranker}), 'scores': scores,
              'hashes': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in [args.data / 'portfolio_items.json', *args.dev.glob('dev_*.json')]},
              'limits': 'Synthetic gold/evidence, retrieval only; 262 no-gold jobs excluded from relevance metrics. Warm shared caches. No judge/decision/reply-rate claim.'}
    (output / 'summary.json').write_text(json.dumps(report, indent=2))
    lines = ['# B2 retrieval comparison', '', report['limits'], '',
             '| Variant | Persona | Recall@5 | MRR | nDCG@10 | p50 ms | p95 ms | Refusals / jobs |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for row in scores:
        lines.append(f"| {row['variant']} | {row['persona']} | {row['recall@5']:.4f} | {row['mrr']:.4f} | {row['ndcg@10']:.4f} | {row['p50_ms']:.2f} | {row['p95_ms']:.2f} | {row['refused']}/{row['jobs']} |")
    (output / 'comparison.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps([s for s in scores if s['persona'] == 'all'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data/processed/kaggle_2024_v1')
    parser.add_argument('--dev', type=Path, default=ROOT / 'evals/datasets/kaggle_2024_v1')
    parser.add_argument('--embedder', choices=['fastembed', 'hashing'], default='fastembed')
    parser.add_argument('--reranker', choices=['fastembed', 'lexical'], default='fastembed')
    asyncio.run(run(parser.parse_args()))
