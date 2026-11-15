# Comparative RAG evaluation

Measured locally on 14 November 2026 using the versioned Kaggle-derived corpus. All portfolio evidence and development relevance labels are synthetic. This experiment measures retrieval, not LLM decision quality, proposal quality, or hiring outcomes.

Three pipelines × seven variants produced 7,098 scored retrieval trials. The development set contains 600 jobs across three personas; 338 have nonempty gold evidence and are scored once per pipeline/variant. The other 262 are excluded from relevance metrics.

| Pipeline | Variant | Recall@5 | MRR@10 | nDCG@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|
| hashing_lexical | v0_naive | 0.2907 | 0.6662 | 0.5220 | 0.2 | 0.4 |
| hashing_lexical | v1_decomposed | 0.3476 | 0.9052 | 0.6123 | 0.8 | 1.2 |
| hashing_lexical | v2_hybrid | 0.3132 | 0.6663 | 0.5514 | 0.2 | 0.3 |
| hashing_lexical | v3_rerank | 0.3462 | 0.7511 | 0.5988 | 0.5 | 0.6 |
| hashing_lexical | v1_v2_hybrid_decomposed | 0.3595 | 0.9144 | 0.6115 | 0.4 | 0.5 |
| hashing_lexical | v1_v2_v3 | 0.3595 | 0.9144 | 0.6115 | 1.6 | 2.2 |
| hashing_lexical | v8_corrective | 0.3621 | 0.9144 | 0.6131 | 0.5 | 0.8 |
| neural_lexical | v0_naive | 0.2600 | 0.6588 | 0.4700 | 8.4 | 10.7 |
| neural_lexical | v1_decomposed | 0.3033 | 0.7762 | 0.5150 | 6.3 | 8.9 |
| neural_lexical | v2_hybrid | 0.3107 | 0.6887 | 0.5469 | 8.0 | 10.6 |
| neural_lexical | v3_rerank | 0.3395 | 0.7570 | 0.5910 | 8.5 | 10.6 |
| neural_lexical | v1_v2_hybrid_decomposed | 0.3487 | 0.8726 | 0.5784 | 13.3 | 18.0 |
| neural_lexical | v1_v2_v3 | 0.3502 | 0.8711 | 0.5796 | 13.7 | 19.1 |
| neural_lexical | v8_corrective | 0.3510 | 0.8729 | 0.5792 | 13.7 | 19.4 |
| neural_cross_encoder | v0_naive | 0.2600 | 0.6588 | 0.4700 | 8.4 | 18.3 |
| neural_cross_encoder | v1_decomposed | 0.3033 | 0.7762 | 0.5150 | 7.3 | 18.3 |
| neural_cross_encoder | v2_hybrid | 0.3107 | 0.6887 | 0.5469 | 8.1 | 10.5 |
| neural_cross_encoder | v3_rerank | 0.2785 | 0.6517 | 0.4994 | 314.5 | 390.2 |
| neural_cross_encoder | v1_v2_hybrid_decomposed | 0.3487 | 0.8726 | 0.5784 | 14.0 | 20.6 |
| neural_cross_encoder | v1_v2_v3 | 0.3206 | 0.8358 | 0.5498 | 14.8 | 158.8 |
| neural_cross_encoder | v8_corrective | 0.3510 | 0.8729 | 0.5792 | 14.1 | 19.0 |

Highest observed Recall@5: **hashing_lexical / v8_corrective** (0.3621). This is a descriptive development-set comparison, not statistical proof of superiority.

The neural embedding model is all-MiniLM-L6-v2 through FastEmbed ONNX. The actual cross-encoder is Xenova/ms-marco-MiniLM-L-6-v2. The lexical reranker and hashing embedding are explicitly identified baselines. Model revisions, artifact hashes, corpus hashes, and per-query ranked evidence are saved alongside the summary.

Latency includes shared-process warm caches and must not be presented as a cold-start or isolated serving benchmark. There is no held-out test or human relevance annotation in this experiment. No application defaults were changed solely from these development scores.

Reproduce with `python -m evals.rd_b.run_neural_retrieval`, then `python -m evals.rd_b.report_neural_retrieval`. Install the embeddings extra and download the two public models first.
