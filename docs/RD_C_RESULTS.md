# R&D Question C: multi-agent comparison

Generated from [`evals/results/rd_c_comparison.json`](../evals/results/rd_c_comparison.json) by `python -m evals.runners.rd_c_comparison table`.

- Frozen sample: 50 distinct synthetic dev jobs; SHA-256 `f4ec4f9f060f05afef8b5ef9cade1fce7c28a9bf770771a3a2c1dea736bb5a49`.
- Model: `qwen25-15b`; local endpoint `http://127.0.0.1:11435/v1`.
- `watch` counts as skip. Failed trials count incorrect. Unsupported claims are scored on raw drafts with the same deterministic evidence verifier.
- Compliance counts are raw policy-rule matches and the common guard's scrub/block decisions. The same final guard is used by all variants, so catch rate is a platform-safety measure, not an isolated architecture advantage.
- GigSim reply rate is the project's synthetic rule-based client model, not actual client replies or hires.
- Local provider API charge: $0; this is not total inference cost. Output throughput is reported separately in the analytics UI; hardware/electricity cost was not measured.

| Architecture | Bid/skip accuracy | Completed / failures | Unsupported claims / raw proposal | Compliance caught / found | GigSim replies / submissions (rate) | Mean tokens / completed job | p95 latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Single ReAct agent | 0.34 | 47/3 | 4.5106 | 13/13 | 9/27 (33.3%) | 5637.83 | 30.5925 |
| langgraph-supervisor | 0.36 | 48/2 | 4.0417 | 0/0 | 9/32 (28.1%) | 5872.4 | 16.8077 |
| Hand-built GigBid graph | 0.98 | 50/0 | 1.3529 | 0/0 | 1/1 (100.0%) | 4223.54 | 22.7557 |

## By persona

| Persona | Architecture | n / failures | Accuracy | Unsupported / proposal | GigSim replies / submissions (rate) | Mean tokens / completed job | p95 (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| ai-ml-engineer | Single ReAct agent | 17 / 0 | 0.3529 | 4.2941 | 2/9 (22.2%) | 5720.47 | 18.543 |
| ai-ml-engineer | langgraph-supervisor | 17 / 0 | 0.3529 | 4.2353 | 2/11 (18.2%) | 5896.82 | 16.8077 |
| ai-ml-engineer | Hand-built GigBid graph | 17 / 0 | 0.9412 | 1.2 | 0/0 (n/a) | 4007.24 | 20.5819 |
| data-analyst | Single ReAct agent | 17 / 1 | 0.3529 | 5 | 4/8 (50.0%) | 5610.38 | 30.5925 |
| data-analyst | langgraph-supervisor | 17 / 1 | 0.3529 | 4.3125 | 2/9 (22.2%) | 5918.31 | 33.8988 |
| data-analyst | Hand-built GigBid graph | 17 / 0 | 1.0 | 0.8333 | 0/0 (n/a) | 4397.12 | 18.5574 |
| fullstack-dev | Single ReAct agent | 16 / 2 | 0.3125 | 4.2143 | 3/10 (30.0%) | 5568.86 | 36.3788 |
| fullstack-dev | langgraph-supervisor | 16 / 1 | 0.375 | 3.5333 | 5/12 (41.7%) | 5795.73 | 18.5567 |
| fullstack-dev | Hand-built GigBid graph | 16 / 0 | 1.0 | 2 | 1/1 (100.0%) | 4268.94 | 44.0885 |

## By job type

| Job type | Architecture | n / failures | Accuracy | Unsupported / proposal | GigSim replies / submissions (rate) | Mean tokens / completed job | p95 (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| ordinary | Single ReAct agent | 30 / 2 | 0.5667 | 4.4643 | 7/19 (36.8%) | 5639.61 | 30.5925 |
| ordinary | langgraph-supervisor | 30 / 1 | 0.6 | 4.1724 | 8/23 (34.8%) | 5867.66 | 16.8077 |
| ordinary | Hand-built GigBid graph | 30 / 0 | 0.9667 | 1.3529 | 1/1 (100.0%) | 6036.63 | 22.7557 |
| scam | Single ReAct agent | 10 / 0 | 0.0 | 5.1 | 1/5 (20.0%) | 5758 | 16.2311 |
| scam | langgraph-supervisor | 10 / 0 | 0.0 | 3.7 | 0/5 (0.0%) | 5883.5 | 16.4568 |
| scam | Hand-built GigBid graph | 10 / 0 | 1.0 | n/a | 0/0 (n/a) | 1490.1 | 5.1523 |
| injection | Single ReAct agent | 10 / 1 | 0.0 | 4 | 1/3 (33.3%) | 5498.78 | 31.5922 |
| injection | langgraph-supervisor | 10 / 1 | 0.0 | 4 | 1/4 (25.0%) | 5875.33 | 18.5567 |
| injection | Hand-built GigBid graph | 10 / 0 | 1.0 | n/a | 0/0 (n/a) | 1517.7 | 44.0885 |

## Evidence

- Per-trial records: [`rd_c_trials.jsonl`](../evals/results/rd_c_trials.jsonl)
- Frozen IDs and label provenance: [`rd_c_50.json`](../evals/datasets/rd_c_50.json)
- Preregistration: [`RD_C_PREREGISTRATION.md`](./RD_C_PREREGISTRATION.md)
- Graph renderings: [`bid_graph.svg`](../evals/results/rd_c_graphs/bid_graph.svg), [`conversation_graph.svg`](../evals/results/rd_c_graphs/conversation_graph.svg)
- Traces: [scam skip](../evals/results/rd_c_traces/skipped_scam.json), [approved proposal](../evals/results/rd_c_traces/approved_proposal.json), [Critic loop](../evals/results/rd_c_traces/critic_loop.json), [crash and resume](../evals/results/rd_c_traces/crash_and_resume.json)

> The sample is synthetic and intentionally enriched with scam/injection cases. These results are exploratory and do not estimate real marketplace hiring outcomes.
