# R&D B component ablation preregistration

**Frozen:** 2026-11-15, before the new ablation run  
**Dataset:** the checked-in GigBid synthetic development corpus; provenance and limitations are documented in [DATA_CARD.md](DATA_CARD.md).  
**Status:** this protocol was written after the earlier exploratory variant results were inspected. Those earlier results motivate the candidate and are not represented as a prospective or independent replication.

## Question and hypothesis

The highest-Recall@5 composed candidate in the prior local comparison was `v1_v2_v3`: V1 requirement decomposition, V2 hybrid dense/BM25 retrieval, and V3 cross-encoder reranking. Does each component contribute to its evidence-retrieval performance?

**Primary hypothesis:** on development jobs with at least one source-level gold evidence item, the full `v1_v2_v3` pipeline will exceed V0 naive by at least **0.10 absolute Recall@5**, and removing any one of decomposition, hybrid retrieval, or reranking will reduce Recall@5 by at least **0.01 absolute** versus the full pipeline.

**Secondary hypothesis:** on eligible jobs with four or more required skills, the full pipeline will exceed V0 by at least **0.15 absolute Recall@5**.

These are directional thresholds, not a significance claim. Failure of any threshold will be reported as a failed hypothesis, without tuning on this test set.

## Conditions and one-factor ablations

| Condition | Decomposition | Hybrid BM25+dense | Cross-encoder |
|---|---:|---:|---:|
| V0 naive reference | No | No | No |
| Full candidate `v1_v2_v3` | Yes | Yes | Yes |
| No decomposition | No | Yes | Yes |
| No hybrid | Yes | No | Yes |
| No reranker | Yes | Yes | No |

Each ablation changes exactly one named component from the full candidate. The same candidate corpus, chunking, FastEmbed model, cross-encoder model, freelancer filter, top-k, jobs, and gold labels are used in every condition. The evaluation is retrieval-only; no decision or proposal outcome is attributed to these retrieval conditions.

## Data, metrics, and analysis

- Evaluate the same 200 synthetic jobs for each of the three personas (600 paired job-persona cases total). Use the existing seed-4016 dev split and its `gold_evidence` source IDs. The corpus and synthetic-label provenance are defined in [DATA_CARD.md](DATA_CARD.md).
- Primary metric: macro mean per-job source-level Recall@5, mapping retrieved chunk IDs to their parent source IDs. Secondary retrieval metric: nDCG@10. Score only cases with nonempty gold evidence; report their count in every stratum.
- Report results by freelancer persona, job category (`job.category`), and synthetic safety type (`normal`, `scam`, `injection`). Scam and injection examples generally have no positive portfolio gold, so Recall/nDCG are **not applicable** there; report their sample counts and returned-evidence/empty-result rates separately, not as zero Recall.
- Also report the secondary comparison on eligible jobs with at least four required skills.
- Pair every condition by job/persona. For full-vs-ablation Recall@5 deltas, report a 95% paired bootstrap interval with 10,000 resamples and seed 4016. Intervals are descriptive; no p-values or generalization claims.
- Preserve per-job output, model metadata, corpus/dev hashes, and the generated summary. Errors fail the run; no rows are silently excluded. No hyperparameter changes are allowed after inspecting these results.

## Separate downstream evidence

Reply-rate evidence comes from the already completed B4 exploratory V0/V8 cohort, not these retrieval-only jobs or the new conditions. Report it as a separate, non-causal comparison. GigSim is a project-owned deterministic simulator, not a real client or hiring outcome. Judge calibration uses the existing 30 author-labeled rubric items; report agreement and Cohen's kappa and keep judge scores explicitly uncalibrated if agreement remains poor.

