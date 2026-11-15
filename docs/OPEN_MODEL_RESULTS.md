# Real open-model comparison results

Source: `evals/results/open_model_comparison.json`. Started 2026-11-14 02:44:14 PKT; finished 2026-11-14 03:04:02 PKT. Raw timestamps remain UTC in the JSON.

Two real open-weight models, 20 identical seeded jobs per persona per model, seed 4016. Excluded 19 persona/job pairs used in the initial prompt-development pilot. Gold labels are synthetic/rule-derived. This is not the full 200-job-per-persona set or an instructor evaluation.

Hardware: NVIDIA RTX 4050 Laptop GPU 6GB; Intel i5-13420H; WSL2 7.6GiB RAM; CUDA12.8; llama.cpp b12359. Endpoint: `http://localhost:11435/v1`. Runtime/model digests: `evals/results/open_model_runtime.json`.

Runtime aliases: `qwen25-15b` = Qwen2.5 1.5B Q4_K_M; `qwen25-05b` = Qwen2.5 0.5B Q4_K_M.

Both conditions hold prompts, graph, retrieval and verifier constant. All LLM roles use the listed model. The graph stops at human approval; proposals are not submitted. The risk prompt was calibrated with safe/unsafe examples after a 1.5B pilot incorrectly flagged a normal project as injection. Pilot attempts and diagnostic outputs remain in `evals/results/open_model_initial_partial.json` and `evals/results/open_model_risk_probe.json`.

| Model | Completed/attempted | Accuracy incl. errors | Bid F1 (completed) | Scam F1 (completed) | Drafts | Unsupported before/after per draft | p50/p95 seconds | Input/output tokens | API USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen25-15b | 59/60 | 0.950 | 0.962 | 0.727 | 25 | 0.720/0.000 | 2.511/9.216 | 147526/23008 | 0 |
| qwen25-05b | 22/60 | 0.283 | 0.000 | 0.400 | 0 | n/a/n/a | 20.238/30.956 | 164453/129908 | 0 |

| Model | Persona | Accuracy incl. errors | Bid F1 | Scam recall | Fair-price-band rate | p95 seconds |
|---|---|---:|---:|---:|---:|---:|
| qwen25-15b | ai-ml-engineer | 0.950 | 0.933 | 0.667 | 1.000 | 9.216 |
| qwen25-15b | fullstack-dev | 0.950 | 0.947 | 1.000 | 0.889 | 9.015 |
| qwen25-15b | data-analyst | 0.950 | 1.000 | 0.333 | 1.000 | 8.512 |
| qwen25-05b | ai-ml-engineer | 0.300 | 0.000 | 0.000 | n/a | 22.073 |
| qwen25-05b | fullstack-dev | 0.200 | 0.000 | 1.000 | n/a | 31.858 |
| qwen25-05b | data-analyst | 0.350 | 0.000 | 0.000 | n/a | 22.605 |

| Model | Tokens/job | Completion tokens/HTTP second | Draft-job p95 seconds |
|---|---:|---:|---:|
| qwen25-15b | 2842.233 | 61.228 | 9.265 |
| qwen25-05b | 4906.017 | 96.751 | n/a |

The smaller model's higher observed completion throughput did not produce faster jobs. Its repeated invalid/truncated JSON consumed tokens and repair attempts; compare token totals, completion coverage and end-to-end latency together. Throughput here includes HTTP overhead and is not a pure decoder benchmark.

## Observed decision/execution failures (46)

Examples below are actual saved cases, not invented labels. Gold is still synthetic.

| Model | Persona | Job | Gold | Model action/error |
|---|---|---|---|---|
| qwen25-15b | ai-ml-engineer | syn-100180 | bid | skip |
| qwen25-15b | fullstack-dev | syn-101017 | bid | skip |
| qwen25-15b | data-analyst | syn-100886 | bid | ValueError |
| qwen25-05b | ai-ml-engineer | syn-100934 | skip | ValueError |
| qwen25-05b | ai-ml-engineer | syn-101281 | bid | ValueError |
| qwen25-05b | ai-ml-engineer | syn-100856 | bid | ValueError |
| qwen25-05b | ai-ml-engineer | inj-200106 | skip | ValueError |
| qwen25-05b | ai-ml-engineer | syn-100665 | bid | ValueError |
| qwen25-05b | ai-ml-engineer | scam-200075 | skip | ValueError |
| qwen25-05b | ai-ml-engineer | syn-100476 | bid | skip |

## Limitations

- Local inference has no API charge; electricity and hardware costs are not measured.
- This is a small development subset following a prompt-development pilot; no significance or generalization claim is made.
- Reported claim support is the lexical verifier's assessment of the final draft pass; it is not human verification.
- Failure rates and null metrics are retained. F1 on completed jobs excludes errors; accuracy including errors penalizes them.
- Latency includes cold loading, queueing and schema-repair calls. Token totals include recorded repairs.
- No calibrated judge, human panel, GigSim outcome or live marketplace outcome was evaluated.

## Local configuration choice

Selected `qwen25-15b` for this local comparison. Selection prioritizes completion rate, then mean bid/scam F1, then accuracy including errors, fewer final unsupported claims, and lower p95 latency. This is a development choice from a small subset, not a production-quality certification.
