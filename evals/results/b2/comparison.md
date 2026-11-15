# B2 retrieval comparison

Synthetic gold/evidence, retrieval only; 262 no-gold jobs excluded from relevance metrics. Warm shared caches. No judge/decision/reply-rate claim.

| Variant | Persona | Recall@5 | MRR | nDCG@10 | p50 ms | p95 ms | Refusals / jobs |
|---|---|---:|---:|---:|---:|---:|---:|
| v0_naive | ai-ml-engineer | 0.3042 | 0.7329 | 0.5354 | 11.57 | 15.94 | 0/200 |
| v0_naive | all | 0.2600 | 0.6588 | 0.4700 | 11.36 | 16.04 | 0/600 |
| v0_naive | fullstack-dev | 0.2147 | 0.5453 | 0.3949 | 11.49 | 15.57 | 0/200 |
| v0_naive | data-analyst | 0.2627 | 0.7043 | 0.4828 | 11.11 | 16.04 | 0/200 |
| v1_decomposed | ai-ml-engineer | 0.3728 | 0.8892 | 0.6353 | 6.82 | 10.31 | 0/200 |
| v1_decomposed | all | 0.3033 | 0.7762 | 0.5150 | 6.96 | 10.56 | 0/600 |
| v1_decomposed | fullstack-dev | 0.2553 | 0.6722 | 0.4047 | 7.48 | 11.32 | 0/200 |
| v1_decomposed | data-analyst | 0.2824 | 0.7705 | 0.5086 | 6.64 | 9.90 | 0/200 |
| v2_hybrid | ai-ml-engineer | 0.3562 | 0.7428 | 0.6131 | 11.15 | 15.47 | 0/200 |
| v2_hybrid | all | 0.3107 | 0.6887 | 0.5469 | 11.43 | 16.87 | 0/600 |
| v2_hybrid | fullstack-dev | 0.2628 | 0.5858 | 0.4646 | 11.88 | 19.07 | 0/200 |
| v2_hybrid | data-analyst | 0.3148 | 0.7437 | 0.5669 | 11.22 | 15.33 | 0/200 |
| v3_rerank | ai-ml-engineer | 0.3119 | 0.6515 | 0.5241 | 452.87 | 561.15 | 0/200 |
| v3_rerank | all | 0.2785 | 0.6517 | 0.4994 | 454.96 | 560.11 | 0/600 |
| v3_rerank | fullstack-dev | 0.2404 | 0.5910 | 0.4244 | 479.49 | 599.84 | 0/200 |
| v3_rerank | data-analyst | 0.2847 | 0.7175 | 0.5547 | 437.26 | 520.36 | 0/200 |
| v8_corrective | ai-ml-engineer | 0.3905 | 0.9027 | 0.6472 | 24.85 | 46.71 | 87/200 |
| v8_corrective | all | 0.3510 | 0.8729 | 0.5792 | 25.47 | 46.71 | 262/600 |
| v8_corrective | fullstack-dev | 0.3194 | 0.8332 | 0.5130 | 25.61 | 45.88 | 83/200 |
| v8_corrective | data-analyst | 0.3438 | 0.8848 | 0.5798 | 25.97 | 47.03 | 92/200 |
