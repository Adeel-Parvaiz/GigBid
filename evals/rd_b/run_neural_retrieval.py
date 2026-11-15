"""Measured retrieval ablations; no heuristic or real LLM decisions are implied."""
import asyncio
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from evals.rd_b.run_real_embedder import (
    DEFAULT_DATA_DIR,
    DEFAULT_DEV_DIR,
    DEFAULT_PERSONAS,
    _load_dev,
    _retrieval_trials,
)
from mcp_servers.marketplace.adapters.sample import SampleAdapter
from rag.index.vector import DenseIndex, FastEmbedder, HashingEmbedder
from rag.retriever import VARIANTS, make_reranker


async def run():
    root = Path(__file__).resolve().parents[2]
    output = root / 'evals/results/neural_rag'
    output.mkdir(parents=True, exist_ok=True)
    items_path = DEFAULT_DATA_DIR / 'portfolio_items.json'
    items = json.loads(items_path.read_text())
    dev = {p: _load_dev(DEFAULT_DEV_DIR / f'dev_{p}.json') for p in DEFAULT_PERSONAS}
    rows, models = [], {}
    cache = str(root / '.local-models/rag-cache')
    for name, embedding, reranking in [('hashing_lexical', 'hashing', 'lexical'),
                                      ('neural_lexical', 'fastembed', 'lexical'),
                                      ('neural_cross_encoder', 'fastembed', 'fastembed')]:
        overrides = {'rag': {'embedder': embedding, 'reranker': reranking, 'cache_dir': cache}}
        from agent.config import load_config
        cfg = load_config(overrides=overrides)
        embedder = HashingEmbedder() if embedding == 'hashing' else FastEmbedder(cache_dir=cache)
        start = time.perf_counter()
        dense = DenseIndex(items, embedder)
        models[name] = {'embedding': getattr(embedder, 'metadata', {'model': 'HashingEmbedder'}),
                        'index_build_seconds': time.perf_counter() - start}
        if reranking == 'fastembed':
            models[name]['reranking'] = make_reranker(cfg).metadata
        result = await _retrieval_trials(items, dense, SampleAdapter(DEFAULT_DATA_DIR), DEFAULT_DATA_DIR,
                                        dev, DEFAULT_PERSONAS, tuple(VARIANTS), name, overrides)
        rows.extend(result)
        (output / 'per_query.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        print(f'{name}: {len(result)} retrieval trials', flush=True)
    groups = defaultdict(list)
    for row in rows:
        groups[row['embedder'], row['variant']].append(row)
    scores = []
    for (pipeline, variant), group in groups.items():
        scores.append({'pipeline': pipeline, 'variant': variant, 'n': len(group),
                       **{metric: float(np.mean([r[metric] for r in group])) for metric in ['recall@5', 'mrr', 'ndcg@10']},
                       'latency_p50_ms': float(np.percentile([r['latency_ms'] for r in group], 50)),
                       'latency_p95_ms': float(np.percentile([r['latency_ms'] for r in group], 95))})
    report = {'scope': 'Retrieval only; synthetic gold and synthetic portfolio evidence; no LLM decisions or human labels.',
              'limitations': ['Queries without gold evidence excluded; no relevance metrics for those queries.',
                              'Shared process caches; latency includes warm-cache effects and is not an isolated serving benchmark.',
                              'Same development set used for comparison; no held-out generalization claim.'],
              'portfolio_sha256': hashlib.sha256(items_path.read_bytes()).hexdigest(),
              'dev_sha256': {p: hashlib.sha256((DEFAULT_DEV_DIR / f'dev_{p}.json').read_bytes()).hexdigest() for p in DEFAULT_PERSONAS},
              'dev_cases': {p: len(cases) for p, cases in dev.items()},
              'models': models, 'scores': scores, 'trials': len(rows)}
    (output / 'summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(scores, indent=2), flush=True)


if __name__ == '__main__':
    asyncio.run(run())
