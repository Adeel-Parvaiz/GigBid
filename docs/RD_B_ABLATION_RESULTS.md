# R&D B — preregistered component ablation

**Run:** `2026-11-14T20:12:21.562228+00:00`. **Data:** synthetic jobs, portfolios, and rule-derived evidence labels only. The preregistration followed inspection of earlier exploratory results; this is not an independent replication. Protocol: [RD_B_PREREGISTRATION.md](RD_B_PREREGISTRATION.md). Dataset provenance: [DATA_CARD.md](DATA_CARD.md).

## Hypothesis and result

Before this run, we predicted that the complete V1 decomposition + V2 dense/BM25 hybrid + V3 cross-encoder pipeline would beat V0 by at least 0.10 absolute Recall@5 on evidence-positive jobs, that each one-component ablation would reduce Recall@5 by at least 0.01, and that the full pipeline would beat V0 by at least 0.15 on evidence-positive jobs with four or more required skills.

The ablation runner explicitly selected FastEmbed for both embeddings and the cross-encoder. The earlier `run_real_embedder.py` composite used the checked-in config's lexical reranker default; therefore its composite score is not a same-model baseline for this run. All ablation comparisons below keep the actual cross-encoder fixed except in the `no_reranking` condition.

- Full-vs-V0 Recall@5 uplift: **0.061**; 0.10 threshold: **not met**.
- Every component removal drops Recall@5 by at least 0.01: **no**.
- 4+ requirements uplift: **0.050** (n=260); 0.15 threshold: **not met**.

## Aggregate retrieval results

Recall@5 and nDCG@10 are averaged over cases with nonempty synthetic source-evidence gold. All 600 job-persona cases are retained for refusal/empty-result and latency reporting. Confidence intervals on full-minus-condition Recall@5 are paired bootstrap intervals (10,000 resamples, seed 4016); they are descriptive and not used as significance tests.

| Condition | Jobs (eligible) | Recall@5 | nDCG@10 | Empty result rate | p95 ms | Δ Recall@5 vs full (95% paired CI) |
|---|---:|---:|---:|---:|---:|---:|
| `v0_naive` | 600 (338) | 0.2600 | 0.4700 | 0.0% | 55.1 | 0.061 [0.042, 0.079] |
| `v1_v2_v3` | 600 (338) | 0.3206 | 0.5498 | 0.0% | 921.9 | reference |
| `no_decomposition` | 600 (338) | 0.2803 | 0.5055 | 0.0% | 1679.1 | 0.040 [0.023, 0.059] |
| `no_hybrid` | 600 (338) | 0.3206 | 0.5498 | 0.0% | 568.7 | 0.000 [0.000, 0.000] |
| `no_reranking` | 600 (338) | 0.3487 | 0.5784 | 0.0% | 47.1 | -0.028 [-0.044, -0.012] |

## Persona breakdown

| Condition | Persona | Jobs (eligible) | Recall@5 | nDCG@10 | Empty result rate |
|---|---|---:|---:|---:|---:|
| `v0_naive` | ai-ml-engineer | 200 (113) | 0.3042 | 0.5354 | 0.0% |
| `v0_naive` | data-analyst | 200 (108) | 0.2627 | 0.4828 | 0.0% |
| `v0_naive` | fullstack-dev | 200 (117) | 0.2147 | 0.3949 | 0.0% |
| `v1_v2_v3` | ai-ml-engineer | 200 (113) | 0.3451 | 0.6117 | 0.0% |
| `v1_v2_v3` | data-analyst | 200 (108) | 0.3345 | 0.5357 | 0.0% |
| `v1_v2_v3` | fullstack-dev | 200 (117) | 0.2842 | 0.5029 | 0.0% |
| `no_decomposition` | ai-ml-engineer | 200 (113) | 0.3086 | 0.5244 | 0.0% |
| `no_decomposition` | data-analyst | 200 (108) | 0.2894 | 0.5623 | 0.0% |
| `no_decomposition` | fullstack-dev | 200 (117) | 0.2447 | 0.4348 | 0.0% |
| `no_hybrid` | ai-ml-engineer | 200 (113) | 0.3451 | 0.6117 | 0.0% |
| `no_hybrid` | data-analyst | 200 (108) | 0.3345 | 0.5357 | 0.0% |
| `no_hybrid` | fullstack-dev | 200 (117) | 0.2842 | 0.5029 | 0.0% |
| `no_reranking` | ai-ml-engineer | 200 (113) | 0.3861 | 0.6457 | 0.0% |
| `no_reranking` | data-analyst | 200 (108) | 0.3426 | 0.5794 | 0.0% |
| `no_reranking` | fullstack-dev | 200 (117) | 0.3184 | 0.5125 | 0.0% |

## Job category breakdown

`job_category` is the synthetic corpus category (not a human-verified occupation label). Cells with no evidence-positive cases report n/a for evidence metrics.

| Condition | Job category | Jobs (eligible) | Recall@5 | nDCG@10 | Empty result rate |
|---|---|---:|---:|---:|---:|
| `v0_naive` | data_analytics | 166 (108) | 0.2627 | 0.4828 | 0.0% |
| `v0_naive` | ml_ai | 212 (113) | 0.3042 | 0.5354 | 0.0% |
| `v0_naive` | web_dev | 222 (117) | 0.2147 | 0.3949 | 0.0% |
| `v1_v2_v3` | data_analytics | 166 (108) | 0.3345 | 0.5357 | 0.0% |
| `v1_v2_v3` | ml_ai | 212 (113) | 0.3451 | 0.6117 | 0.0% |
| `v1_v2_v3` | web_dev | 222 (117) | 0.2842 | 0.5029 | 0.0% |
| `no_decomposition` | data_analytics | 166 (108) | 0.2894 | 0.5623 | 0.0% |
| `no_decomposition` | ml_ai | 212 (113) | 0.3086 | 0.5244 | 0.0% |
| `no_decomposition` | web_dev | 222 (117) | 0.2447 | 0.4348 | 0.0% |
| `no_hybrid` | data_analytics | 166 (108) | 0.3345 | 0.5357 | 0.0% |
| `no_hybrid` | ml_ai | 212 (113) | 0.3451 | 0.6117 | 0.0% |
| `no_hybrid` | web_dev | 222 (117) | 0.2842 | 0.5029 | 0.0% |
| `no_reranking` | data_analytics | 166 (108) | 0.3426 | 0.5794 | 0.0% |
| `no_reranking` | ml_ai | 212 (113) | 0.3861 | 0.6457 | 0.0% |
| `no_reranking` | web_dev | 222 (117) | 0.3184 | 0.5125 | 0.0% |

## Persona × job category

| Condition | Persona / category | Jobs (eligible) | Recall@5 | nDCG@10 |
|---|---|---:|---:|---:|
| `v0_naive` | ai-ml-engineer / data_analytics | 28 (0) | n/a | n/a |
| `v0_naive` | ai-ml-engineer / ml_ai | 113 (113) | 0.3042 | 0.5354 |
| `v0_naive` | ai-ml-engineer / web_dev | 59 (0) | n/a | n/a |
| `v0_naive` | data-analyst / data_analytics | 108 (108) | 0.2627 | 0.4828 |
| `v0_naive` | data-analyst / ml_ai | 46 (0) | n/a | n/a |
| `v0_naive` | data-analyst / web_dev | 46 (0) | n/a | n/a |
| `v0_naive` | fullstack-dev / data_analytics | 30 (0) | n/a | n/a |
| `v0_naive` | fullstack-dev / ml_ai | 53 (0) | n/a | n/a |
| `v0_naive` | fullstack-dev / web_dev | 117 (117) | 0.2147 | 0.3949 |
| `v1_v2_v3` | ai-ml-engineer / data_analytics | 28 (0) | n/a | n/a |
| `v1_v2_v3` | ai-ml-engineer / ml_ai | 113 (113) | 0.3451 | 0.6117 |
| `v1_v2_v3` | ai-ml-engineer / web_dev | 59 (0) | n/a | n/a |
| `v1_v2_v3` | data-analyst / data_analytics | 108 (108) | 0.3345 | 0.5357 |
| `v1_v2_v3` | data-analyst / ml_ai | 46 (0) | n/a | n/a |
| `v1_v2_v3` | data-analyst / web_dev | 46 (0) | n/a | n/a |
| `v1_v2_v3` | fullstack-dev / data_analytics | 30 (0) | n/a | n/a |
| `v1_v2_v3` | fullstack-dev / ml_ai | 53 (0) | n/a | n/a |
| `v1_v2_v3` | fullstack-dev / web_dev | 117 (117) | 0.2842 | 0.5029 |
| `no_decomposition` | ai-ml-engineer / data_analytics | 28 (0) | n/a | n/a |
| `no_decomposition` | ai-ml-engineer / ml_ai | 113 (113) | 0.3086 | 0.5244 |
| `no_decomposition` | ai-ml-engineer / web_dev | 59 (0) | n/a | n/a |
| `no_decomposition` | data-analyst / data_analytics | 108 (108) | 0.2894 | 0.5623 |
| `no_decomposition` | data-analyst / ml_ai | 46 (0) | n/a | n/a |
| `no_decomposition` | data-analyst / web_dev | 46 (0) | n/a | n/a |
| `no_decomposition` | fullstack-dev / data_analytics | 30 (0) | n/a | n/a |
| `no_decomposition` | fullstack-dev / ml_ai | 53 (0) | n/a | n/a |
| `no_decomposition` | fullstack-dev / web_dev | 117 (117) | 0.2447 | 0.4348 |
| `no_hybrid` | ai-ml-engineer / data_analytics | 28 (0) | n/a | n/a |
| `no_hybrid` | ai-ml-engineer / ml_ai | 113 (113) | 0.3451 | 0.6117 |
| `no_hybrid` | ai-ml-engineer / web_dev | 59 (0) | n/a | n/a |
| `no_hybrid` | data-analyst / data_analytics | 108 (108) | 0.3345 | 0.5357 |
| `no_hybrid` | data-analyst / ml_ai | 46 (0) | n/a | n/a |
| `no_hybrid` | data-analyst / web_dev | 46 (0) | n/a | n/a |
| `no_hybrid` | fullstack-dev / data_analytics | 30 (0) | n/a | n/a |
| `no_hybrid` | fullstack-dev / ml_ai | 53 (0) | n/a | n/a |
| `no_hybrid` | fullstack-dev / web_dev | 117 (117) | 0.2842 | 0.5029 |
| `no_reranking` | ai-ml-engineer / data_analytics | 28 (0) | n/a | n/a |
| `no_reranking` | ai-ml-engineer / ml_ai | 113 (113) | 0.3861 | 0.6457 |
| `no_reranking` | ai-ml-engineer / web_dev | 59 (0) | n/a | n/a |
| `no_reranking` | data-analyst / data_analytics | 108 (108) | 0.3426 | 0.5794 |
| `no_reranking` | data-analyst / ml_ai | 46 (0) | n/a | n/a |
| `no_reranking` | data-analyst / web_dev | 46 (0) | n/a | n/a |
| `no_reranking` | fullstack-dev / data_analytics | 30 (0) | n/a | n/a |
| `no_reranking` | fullstack-dev / ml_ai | 53 (0) | n/a | n/a |
| `no_reranking` | fullstack-dev / web_dev | 117 (117) | 0.3184 | 0.5125 |

## Synthetic safety-type breakdown

Correction to the preregistration's data-stratum expectation: 22 scam and 16 injection rows had nonempty synthetic evidence gold. Their retrieval scores are included over those eligible rows. Recall/nDCG are undefined only for rows with no gold; the table gives eligible counts and empty-result rates.

| Condition | Type | Jobs | Eligible evidence jobs | Recall@5 | Empty result rate | Mean returned sources |
|---|---|---:|---:|---:|---:|---:|
| `v0_naive` | normal | 480 | 300 | 0.2654 | 0.0% | 10.00 |
| `v0_naive` | scam | 70 | 22 | 0.1818 | 0.0% | 10.00 |
| `v0_naive` | injection | 50 | 16 | 0.2656 | 0.0% | 10.00 |
| `v1_v2_v3` | normal | 480 | 300 | 0.3196 | 0.0% | 9.06 |
| `v1_v2_v3` | scam | 70 | 22 | 0.3125 | 0.0% | 8.86 |
| `v1_v2_v3` | injection | 50 | 16 | 0.3516 | 0.0% | 9.02 |
| `no_decomposition` | normal | 480 | 300 | 0.2833 | 0.0% | 10.00 |
| `no_decomposition` | scam | 70 | 22 | 0.2216 | 0.0% | 10.00 |
| `no_decomposition` | injection | 50 | 16 | 0.3047 | 0.0% | 10.00 |
| `no_hybrid` | normal | 480 | 300 | 0.3196 | 0.0% | 9.06 |
| `no_hybrid` | scam | 70 | 22 | 0.3125 | 0.0% | 8.86 |
| `no_hybrid` | injection | 50 | 16 | 0.3516 | 0.0% | 9.02 |
| `no_reranking` | normal | 480 | 300 | 0.3475 | 0.0% | 9.28 |
| `no_reranking` | scam | 70 | 22 | 0.3636 | 0.0% | 9.19 |
| `no_reranking` | injection | 50 | 16 | 0.3516 | 0.0% | 9.24 |

## Did retrieval improvement translate to replies?

No measurable increase appeared in the existing B4 V0/V8 exploratory comparison: the B2 neural retrieval benchmark reported V0 Recall@5/nDCG@10 of 0.2600/0.4700 and V8 of 0.3510/0.5792, while B4 recorded 18/37 (48.6%) versus 17/35 (48.6%) simulated replies per submitted proposal. These are different cohorts and variants; this is not a paired causal test, and it does not establish that retrieval has no effect.

The project-owned `LocalSimAdapter` computes reply probability from required-skill mentions in the proposal text, bid amount versus a hidden ceiling, title-word personalization, and a generic-opening penalty. It does not reward Recall@5 or evidence rank directly. Retrieval can therefore improve without changing the drafted wording, affordability, personalization, or whether the proposal passes submission gates. Only submitted proposals enter the reply denominator; small denominators and rule-derived synthetic outcomes further limit the comparison.

| B4 variant | Persona | Type | Submitted with matched outcome | Replies | Reply rate |
|---|---|---|---:|---:|---:|
| `v0_naive` | ai-ml-engineer | injection | 0 | 0 | n/a |
| `v0_naive` | ai-ml-engineer | normal | 10 | 5 | 50.0% |
| `v0_naive` | ai-ml-engineer | scam | 0 | 0 | n/a |
| `v0_naive` | data-analyst | injection | 0 | 0 | n/a |
| `v0_naive` | data-analyst | normal | 14 | 8 | 57.1% |
| `v0_naive` | data-analyst | scam | 0 | 0 | n/a |
| `v0_naive` | fullstack-dev | injection | 0 | 0 | n/a |
| `v0_naive` | fullstack-dev | normal | 13 | 5 | 38.5% |
| `v0_naive` | fullstack-dev | scam | 0 | 0 | n/a |
| `v8_corrective` | ai-ml-engineer | injection | 0 | 0 | n/a |
| `v8_corrective` | ai-ml-engineer | normal | 7 | 4 | 57.1% |
| `v8_corrective` | ai-ml-engineer | scam | 0 | 0 | n/a |
| `v8_corrective` | data-analyst | injection | 0 | 0 | n/a |
| `v8_corrective` | data-analyst | normal | 13 | 6 | 46.2% |
| `v8_corrective` | data-analyst | scam | 0 | 0 | n/a |
| `v8_corrective` | fullstack-dev | injection | 0 | 0 | n/a |
| `v8_corrective` | fullstack-dev | normal | 15 | 7 | 46.7% |
| `v8_corrective` | fullstack-dev | scam | 0 | 0 | n/a |

## Judge calibration

The existing proposal judge calibration used **30** author-labeled items; agreement was **36.7%** and unweighted Cohen's κ was **0.000** (status: `calibration_measured`). With κ=0, rubric scores are not calibrated and are not used to select the retrieval variant. The blind classmate panel remains `pending_classmates`.

## Shipping decision

Keep `v1_decomposed` as the configured shipping variant. The combined V1+V2+V3 candidate and its one-factor ablations are development-only: even a retrieval win is not a demonstrated improvement in human-rated proposal quality or client replies, and the available GigSim reply rates did not rise from V0 to V8. The local judge has κ=0, the outcomes are synthetic, and the new ablation has no independent instructor labels. Reconsider shipping only after matched proposal/outcome evaluation and usable human calibration; do not promote the composite solely on Recall@5.

## Reproduction and artifacts

- Run the frozen retrieval experiment: `python -m evals.rd_b.run_ablation`.
- Regenerate this report/table from saved run artifacts: `python -m evals.rd_b.report_ablation`.
- Variant composition: `evals/rd_b/ablation_variants.py`; raw per-job rows: `evals/rd_b/results/ablation_per_job.jsonl`; model/data manifest: `evals/rd_b/results/ablation_run.json`; summarized metrics: `evals/rd_b/results/ablation_summary.json`.
- Prior B2/B4 results and calibration inputs are retained separately; see `evals/results/b2/summary.json`, `evals/results/b4_exploratory/summary.json`, `agent/config.yaml`, and `docs/DATA_CARD.md`.
