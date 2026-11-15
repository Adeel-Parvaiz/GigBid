"""Render the measured neural retrieval results without implying live job outcomes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    report = json.loads((ROOT / 'evals/results/neural_rag/summary.json').read_text())
    lines = ['# Comparative RAG evaluation', '',
             'Measured locally on 14 November 2026 using the versioned Kaggle-derived corpus. '
             'All portfolio evidence and development relevance labels are synthetic. '
             'This experiment measures retrieval, not LLM decision quality, proposal quality, or hiring outcomes.', '',
             f"Three pipelines × seven variants produced {report['trials']:,} scored retrieval trials. "
             'The development set contains 600 jobs across three personas; 338 have nonempty gold evidence '
             'and are scored once per pipeline/variant. The other 262 are excluded from relevance metrics.', '',
             '| Pipeline | Variant | Recall@5 | MRR@10 | nDCG@10 | p50 ms | p95 ms |',
             '|---|---|---:|---:|---:|---:|---:|']
    for s in report['scores']:
        lines.append(f"| {s['pipeline']} | {s['variant']} | {s['recall@5']:.4f} | {s['mrr']:.4f} | {s['ndcg@10']:.4f} | {s['latency_p50_ms']:.1f} | {s['latency_p95_ms']:.1f} |")
    best = max(report['scores'], key=lambda s: s['recall@5'])
    lines.extend(['', f"Highest observed Recall@5: **{best['pipeline']} / {best['variant']}** "
                  f"({best['recall@5']:.4f}). This is a descriptive development-set comparison, not statistical proof of superiority.", '',
                  'The neural embedding model is all-MiniLM-L6-v2 through FastEmbed ONNX. '
                  'The actual cross-encoder is Xenova/ms-marco-MiniLM-L-6-v2. '
                  'The lexical reranker and hashing embedding are explicitly identified baselines. '
                  'Model revisions, artifact hashes, corpus hashes, and per-query ranked evidence are saved alongside the summary.', '',
                  'Latency includes shared-process warm caches and must not be presented as a cold-start or isolated serving benchmark. '
                  'There is no held-out test or human relevance annotation in this experiment. '
                  'No application defaults were changed solely from these development scores.', '',
                  'Reproduce with `python -m evals.rd_b.run_neural_retrieval`, then '
                  '`python -m evals.rd_b.report_neural_retrieval`. Install the embeddings extra and download the two public models first.'])
    (ROOT / 'docs/NEURAL_RAG_RESULTS.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
