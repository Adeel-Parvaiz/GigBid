# AI-4016 | R&D ASSIGNMENT | GIGBID

## Engineering design review

**Review date:** 15 November 2026  
**Prepared for:** AI-4016  
**Author:** Muhammad Adeel 23i-0739  
**Status:** Measured prototype with explicit open items. Main report is limited to ten pages; appendices follow.

### Executive decision

The measured B2 retrieval winner among the five required variants is V8 corrective (Recall@5 0.3510; nDCG@10 0.5792). The shipped configuration remains V1 decomposed; the synthetic development results do not alone justify changing that default. The separate B4 exploratory sample measured the local proposal/GigSim workflow, but is not the full 1,200-run protocol. Human calibration has zero measured agreement beyond chance, the classmate panel is pending, and no real marketplace outcome is claimed. [E04][E06]

## 1. Problem and constraints

GigBid supports a freelancer from job discovery through job analysis, portfolio matching, bid/skip and pricing decisions, proposal drafting, client-message handling, and follow-up scheduling. The primary corpus contains real text from Kaggle job posts, but freelancer histories, client histories, development gold labels, and simulator outcomes are synthetic. The source has no reply/hire labels and no currency column. [E02]

**Must never be automated:** sending a proposal or client message, spending Connects, approving an edited draft, or bypassing a human review. Live Upwork writes require both GigBid approval and a separate platform-confirmation action. [E03]

**Budgets:** the checked-in config sets 30 graph steps, at most two Critic revisions, and a 12,000-token-per-job cap. Both graphs enforce step and token limits; the LLM adapter caps each response to the remaining allowance, and exhaustion moves the run to visible `needs_attention`. No p95-latency target or dollar-cost ceiling was recorded. [E01][E12]

Measured reference points, not acceptance thresholds: B2 retrieval p95 was about 16 ms for V0 and 47 ms for V8. In B4, end-to-end p95 for successful proposals was 51.08 s for V0 and 53.43 s for V8; the provider API charge was $0, but that is not the total cost of local inference. The open profile reports output tokens/sec and a hardware note; hardware/electricity cost was not measured. The paid profile reports USD only from exact input/output token usage and configured per-model rates; unknown prices or inexact usage are shown as n/a. No paid-profile cost was measured in these results. Proposal-stage token means by persona were 13.4k-17.6k, above the configured 12k value. [E04][E06]

**[PLACEHOLDER]** Before hidden testing, declare acceptable end-to-end p95 latency and fully loaded cost per proposal, including how local hardware/electricity is estimated.

[[PAGEBREAK]]

## 2. Architecture

The bid graph loads job/client data, then runs analyst, risk, and fit/retrieval work in parallel; deterministic decision and pricing nodes feed a writer, claim verifier, and bounded Critic loop, followed by compliance and a human interrupt before submission. The conversation graph loads a thread, classifies intent, proposes slots, drafts a reply, checks compliance, and also pauses for approval before send. [E01]

| Component | Responsibility and reason |
|---|---|
| Analyst / Risk | Convert job text to a structured spec; identify scams, free-work requests, off-platform requests, and injection. Rules provide a floor; the model may add risk but not lower it. |
| Fit Matcher / Decide / Pricing | Retrieve portfolio evidence; make an explainable threshold-based bid/watch/skip choice; price against budget, user floor, and Connects. Deterministic work avoids unnecessary model cost. |
| Writer / Verifier / Critic | Draft evidence-linked claims, remove unsupported claims before critique, and review grounding, relevance, and length with at most two revisions. |
| Liaison / Compliance | Classify client intent, use code-owned calendar slots, draft responses, and apply policy checks before the human approval interrupt. |
| Marketplace port / MCP | Route sample, project-owned GigSim, or authorized Upwork operations through the same port. Portfolio, Marketplace, and Workspace MCP servers expose 15 project tools with schema tests. |
| Stores and trace | Typed graph state/reducers, audit traces, and promoted memory are separate. API/worker share PostgreSQL-backed `AsyncPostgresStore` when `DATABASE_URL` is set; local/tests without it use volatile `InMemoryStore`. LangGraph checkpoints support restart recovery; authenticated history and replay APIs branch from a run-owned checkpoint at a selected graph node. The integration suite includes Postgres crash-resume/idempotency and API-restart tests. GigSim persists synthetic state and idempotency records in SQLite. [E12] |

The split is intentional: models handle language and evidence selection; code owns thresholds, policy enforcement, calendar facts, approval, and writes. Step, revision, and token limits are enforced. Per-node timeouts and bounded retries cover transient failures, configured cheap-node fallback models cover provider failures, and unrecoverable pre-write failures become visible dead letters; uncertain post-approval failures require human attention. Mutating nodes are not automatically retried. [E01][E03][E12]

Usage accounting is profile-aware: the analytics UI reports input/output tokens, output tokens/sec, latency, and trace links for each analyzed run. Paid API cost is calculated only when exact per-model input/output usage and configured rates are available; otherwise it is n/a. Local inference is not converted to dollars and is accompanied by a hardware/electricity note. Heuristic test runs are identified separately and their estimated tokens are not billed as model usage.

[[PAGEBREAK]]

## 3. R&D question A - tool granularity

**Question:** does exposing fine-grained MCP tools improve a model's choice and arguments compared with combined tools? The measured expectation is that narrower names/schemas reduce ambiguity. This expectation is reconstructed for this report; no preregistered hypothesis was recorded. [E05]

**Setup:** 40 authored, schema-grounded tasks were run under each of three conditions using local Qwen2.5 1.5B, temperature 0, and actual official-SDK MCP sessions: 15 fine tools; three combined server tools; and the best set with rewritten descriptions. The same seeded task set covered all 15 operations. [E05]

| Condition | Tool choice | Exact arguments | Successful result | Mean tokens/task |
|---|---:|---:|---:|---:|
| 15 fine-grained tools | 95.0% | 82.5% | 90.0% | 2,631 |
| 3 combined tools | 30.0% | 15.0% | 15.0% | 2,687 |
| Best fine set, rewritten descriptions | 90.0% | 75.0% | 87.5% | 2,809 |

**Conclusion:** fine-grained tools exceeded combined tools by 65 percentage points on tool choice and 67.5 points on exact arguments for this task set. Rewriting descriptions reduced choice accuracy by 5 points versus the fine base. This is one local model, one sample per task, and a curated synthetic task set; it is not a general model ranking or evidence that production tool routing changed. [E05]

[[PAGEBREAK]]

## 4. R&D question B - RAG, claim verification, and ablation

**Status: COMPLETE for the scoped R&D B deliverables.** The hypothesis was frozen before the one-factor ablation, and the outcome is reported honestly: the preregistered thresholds were not met. The package includes the dataset card ([`docs/DATA_CARD.md`](docs/DATA_CARD.md)), variant composition ([`evals/rd_b/ablation_variants.py`](evals/rd_b/ablation_variants.py)), and a report/table regeneration command ([`evals/rd_b/report_ablation.py`](evals/rd_b/report_ablation.py)). Judge calibration and the shipping decision are reported below. This completion status does not imply the separate full B4 protocol or classmate panel is complete. [E06][E11]

**Setup and hypothesis status:** the original five-variant B2 comparison used the same 600 synthetic development jobs per variant; 338 had nonempty synthetic evidence gold. That run was exploratory. Before a subsequent one-factor ablation, the protocol predicted that the composite V1 decomposition + V2 dense/BM25 hybrid + V3 cross-encoder pipeline would beat V0 by at least 0.10 Recall@5, each one-component removal would lower Recall@5 by at least 0.01, and the 4+ required-skill uplift would be at least 0.15. The protocol followed inspection of earlier variant results, so the new run is preregistered relative to its own execution, not an independent replication. [E04][E11]

| Variant | Recall@5 | nDCG@10 | Retrieval p95 |
|---|---:|---:|---:|
| V0 naive | 0.2600 | 0.4700 | 16 ms |
| V1 decomposed | 0.3033 | 0.5150 | 11 ms |
| V2 hybrid | 0.3107 | 0.5469 | 17 ms |
| V3 rerank | 0.2785 | 0.4994 | 560 ms |
| V8 corrective | 0.3510 | 0.5792 | 47 ms |

V8 has the highest aggregate retrieval scores among the five required variants. V3 is a negative result: its measured Recall@5 was below V0 while p95 latency was far higher. V8 refused evidence on 262/600 cases; those are retrieval refusals, not scam or bid/skip decisions. Results are descriptive, with no significance claim. [E04]

The new matched ablation scored 600 jobs per condition (338 with positive gold). Full V1+V2+V3 Recall@5 was 0.3206 vs V0 0.2600: +0.0607, below the preregistered +0.10 threshold. Removing decomposition reduced Recall@5 to 0.2803; removing hybrid left it unchanged at 0.3206; removing reranking improved it to 0.3487 and cut p95 from 921.9 ms to 47.1 ms. On 4+ skill cases (n=260), uplift was +0.050, below +0.15. Both primary and secondary hypotheses were not met. The no-reranker condition's measured paired Recall@5 gain over the full candidate was +0.0281. [E11]

The new runner explicitly used the FastEmbed cross-encoder. The earlier composite in `run_real_embedder.py` used the checked-in config's lexical reranker default, so its score is not a same-model baseline; the reported one-factor deltas are within this new run. [E01][E11]

Breakdowns by persona, synthetic job category, synthetic safety type, plus the paired intervals and B4 reply-rate comparison are in the generated ablation report. The preregistration expected scam/injection rows to usually lack gold; 22 scam and 16 injection rows in this split did have positive gold and are scored as eligible. Recall is undefined only for the remaining no-gold rows. [E11]

The B3 real-model claim check labeled 6/43 claim units unsupported before filtering and 0/22 after rechecking; two of 12 drafts were emptied and blocked rather than counted as good proposals. Evidence is synthetic, labels come from the verifier, and semantic truth is not independently established. [E07]

The current configured variant is `v1_decomposed`, not V8 or the V1+V2+V3 experimental composite. Keep V1 shipping: this synthetic retrieval experiment does not demonstrate a human-rated or client-reply gain, the judge has κ=0, and the cross-encoder both worsened retrieval and substantially increased latency in the matched ablation. [E01][E04][E06][E11]

[[PAGEBREAK]]

## 4. R&D question B - integrated B5 results

The requested table joins B2 retrieval results with B4 proposal and simulator results. These columns come from separate cohorts: B2 uses 600 jobs; B4 uses 50 sampled jobs per persona and variant (300 attempts). The B4 sample recorded 295 completed decisions, five model/output errors, and 95 eligible proposals, all rubric-scored. [E04][E06]

| Variant | Evidence Recall@5 | Evidence nDCG@10 | Unsupported claims / proposal | Judge score (0-4) | GigSim reply rate | p95 latency (s) | Cost / proposal (USD) |
|---|---:|---:|---:|---:|---:|---:|---:|
| V0 naive | 0.2600 | 0.4700 | 0.00 (0/45) | 3.00 (n=45; uncalibrated) | 48.6% (18/37) | 51.08 | n/a* |
| **Your best: V8 corrective** | **0.3510** | **0.5792** | 0.00 (0/50) | 2.94 (n=50; uncalibrated) | 48.6% (17/35) | 53.43 | n/a* |

V8 is selected as “Your best” on aggregate B2 Recall@5 and nDCG@10 only; it is not a statistically established overall winner. Unsupported-claim counts are post-verifier model labels. Judge calibration on 30 author-labeled items was 11/30 agreement (36.7%), Cohen's kappa 0.000; judge scores are not calibrated. Replies are from project-owned scripted GigSim among submitted proposals, not real hiring. P95 is full graph latency for successfully produced proposals. *USD inference cost is n/a for these local runs: provider API charge was $0, but hardware/electricity cost is unknown. The full B4 protocol remains paused at 16/1,200 and classmate votes are pending. [E04][E06]

The B4 persona and synthetic job-type slices are in Appendix B. Scam recall in this sample was low (7/23 flagged in each variant); injection detection was 9/10 for V0 and 9/11 for V8. These are small, rule-labeled synthetic slices. [E06]

[[PAGEBREAK]]

## 5. R&D question C - single agent vs supervisor vs graph

**Status: RUN.** The same local Qwen model, tools, evidence corpus, and budgets were used for all three variants on 50 frozen distinct synthetic jobs (150 paired trials). Five trials failed validation/provider calls and count as incorrect: three ReAct and two supervisor; the hand-built graph completed all 50. [E13]

| Architecture | Bid/skip accuracy | Unsupported claims / raw proposal | Compliance caught / found | GigSim replies / submissions | Mean tokens / completed job | p95 latency (s) |
|---|---:|---:|---:|---:|---:|---:|
| Single ReAct agent | 0.34 | 4.51 | 13 / 13 | 9 / 27 (33.3%) | 5,638 | 30.59 |
| `langgraph-supervisor` | 0.36 | 4.04 | 0 / 0 | 9 / 32 (28.1%) | 5,872 | 16.81 |
| Hand-built GigBid graph | **0.98** | **1.35** | 0 / 0 | 1 / 1 (100%) | **4,224** | 22.76 |

On this sample, the hand-built graph had higher accuracy on ordinary jobs (0.967) and scam/injection jobs (1.00); ReAct and the supervisor scored 0.00 on scam/injection and did not beat the graph on any job-type slice. The graph used fewer mean tokens than both baselines, but its p95 latency was slower than the supervisor. Reply rates are simulator-only and denominators matter: the graph's 100% is one reply from one submission. ReAct and supervisor submitted 15/27 and 18/32 proposals on gold-skip jobs. One ReAct proposal on an injection-labeled skip job passed the current gate, contained five unsupported claim units, and received a synthetic reply; its trace shows risk score 0.3 and no rule-matched compliance violation. This is a material safety limitation, not a successful outcome. The local provider API charge was $0; hardware/electricity was not measured and local inference cost is not zero. Synthetic rule-derived labels, a risk-enriched sample, and one local model prevent generalization to real client behavior. [E13]

The full persona/job-type tables, preregistration, raw trials, graph renderings, and traces are in [`docs/RD_C_RESULTS.md`](docs/RD_C_RESULTS.md), [`evals/results/rd_c_comparison.json`](evals/results/rd_c_comparison.json), and [`evals/results/rd_c_trials.jsonl`](evals/results/rd_c_trials.jsonl). The skipped-scam, approved-proposal, Critic-loop, and crash/resume trace links are included there. The latter points to the existing PostgreSQL durability test; it is not one of the 50 comparison trials. [E13]

## 6. Change request

**Status: NOT RECEIVED.** The report checklist records no change request as of this report. No edit duration or line count is invented. [E10]

**[PLACEHOLDER]** Request/date: TBD. Before/after behavior: TBD. Files/lines changed: TBD. Elapsed engineering time: TBD. Regression results and design implication: TBD.

[[PAGEBREAK]]

## 7. Signature extension

**Status: NOT BUILT.** The extension record explicitly says no X1-X6 extension has been implemented or measured. A suggested proposal experiment is not an implemented extension. [E10]

**[PLACEHOLDER]** Select and build one extension. Record its user-visible signature, baseline, evaluation protocol, results, safety impact, and reproduction command. Do not mark this section complete until the experiment has run.

[[PAGEBREAK]]

## 8. Failure analysis

Ten unique failed development jobs are enumerated in Appendix A, grouped as model-output failures and wrong skips. The only paired fix measured for these examples was switching from Qwen2.5 0.5B to 1.5B: the 1.5B run completed 59/60 versus 22/60 for 0.5B. In the ten paired examples, seven failures were corrected; three remained failures (one persistent output failure and two wrong skips). This is a model-selection intervention, not a job-specific prompt fix. [E08]

Other observed failures include five B4 model/output errors, low scam detection in the B4 synthetic cohort, and a paraphrased-injection blind spot. The real-agent behavior run initially failed five checks across 22, then passed 25/25 after corrections to failed-state persistence, duplicate starts, edited-claim grounding, liaison routing, calendar dates, and Critic length checks. [E06][E08][E09]

**Taxonomy status:** output/schema errors, wrong skips, scam/injection misses, and pricing errors are measurable; generic openings and job-specific compliance misses do not yet have a unified ten-case trace/fix table. Appendix A separates observed fixes from unresolved work. [E06][E08][E09]

**[PLACEHOLDER]** Add a per-case attempted fix and rerun result for the remaining misses; add representative generic-opening and compliance misses if they occur. Do not relabel an untested intervention as successful.

[[PAGEBREAK]]

## 9. Safety and platform respect

No proposal or message is sent and no Connects are spent before human approval. Blocked proposals cannot be approved; user edits are rechecked; write operations are not automatically retried after uncertain failures. Role allowlists restrict MCP discovery and calls. Live Upwork additionally requires an explicit second confirmation bound to the reviewed preview. These controls have unit, protocol, and local browser evidence. [E03][E09]

GigBid uses the official Upwork MCP rather than scraping. Live OAuth and read-only account/job/client/balance/room reads succeeded; no live proposal or message write was made. Synthetic profiles are blocked from live proposals. GigSim outcomes are a project-owned deterministic simulator and never evidence of real hiring. [E02][E03]

Known gaps: the paraphrased unseen injection set had 100% attack success in the labeled fixture; B4 scam recall was 25-37.5% by persona; the model verifier and judge are not independent human truth checks; and the judge has kappa 0.000. These findings limit safety claims and require further red-team and human review. [E06][E07][E09]

[[PAGEBREAK]]

## 10. Hidden tests and declared budgets

**Hidden tests: NOT RUN / NOT PROVIDED.** The instructor's immutable GigSim package and hidden test set were unavailable. No hidden-test pass rate or hidden marketplace result is claimed. [E02][E10]

**Declared-vs-measured status:**

- `max_graph_steps=30` and `max_revisions=2` are configured; revision-limit behavior is covered in local real-agent checks. [E01][E09]
- `max_tokens_per_job=12,000` is present in config but is not referenced elsewhere in the source search. B4 proposal-stage mean token usage by persona was 13.4k-17.6k, so the configured value is not verified as enforced and cannot be reported as passed. [E01][E06]
- No latency SLA or fully loaded cost ceiling was declared. Measured local reference p95 is reported in Sections 1 and 4; local inference API cost is $0, hardware/electricity remains unknown. [E04][E06]
- No hidden-test result can be compared with a budget until the instructor test is run and thresholds are declared.

**[PLACEHOLDER]** Insert hidden-test artifact path, date, case counts, failures, p95, tokens, cost, and comparison to the declared thresholds. If test data or budgets are unavailable at submission, state “not available / not run,” not “passed.”

[[PAGEBREAK]]

# Appendices

## Appendix A. Ten paired failed development cases

These are unique job IDs from the saved two-model comparison. “Fix” is the measured 1.5B-for-0.5B model switch; it improved aggregate completion but does not prove a reusable per-case repair. [E08]

| Failure class | Job ID | Qwen2.5 0.5B | Qwen2.5 1.5B | Fix tried and measured outcome |
|---|---|---|---|---|
| Output/schema failure | syn-100934 | Incomplete | Correct skip | Model switch corrected this paired case. |
| Output/schema failure | syn-101281 | Incomplete | Correct bid | Model switch corrected this paired case. |
| Output/schema failure | syn-100856 | Incomplete | Correct bid | Model switch corrected this paired case. |
| Output/schema failure | inj-200106 | Incomplete | Correct skip | Model switch corrected this paired case. |
| Output/schema failure | syn-100665 | Incomplete | Correct bid | Model switch corrected this paired case. |
| Output/schema failure | scam-200075 | Incomplete | Correct skip | Model switch corrected this paired case. |
| Wrong skip | syn-100476 | Incorrect skip | Correct bid | Model switch corrected this paired case. |
| Output failure -> wrong skip | syn-100180 | Incomplete | Incorrect skip (gold bid) | Larger model produced a decision but did not fix the decision. |
| Wrong skip | syn-101017 | Incorrect skip | Incorrect skip (gold bid) | Not corrected by model switch; further fix not measured. |
| Persistent output failure | syn-100886 | Incomplete | Incomplete | Not corrected by model switch; further fix not measured. |

The comparison as a whole recorded 59/60 completed jobs for Qwen2.5 1.5B and 22/60 for Qwen2.5 0.5B. Exact source records are in `evals/results/open_model_comparison.json`; the documented examples and aggregate are in `docs/OPEN_MODEL_RESULTS.md`. [E08]

## Appendix B. Persona and job-type detail

### B2 retrieval by persona

| Persona | V0 Recall@5 / nDCG@10 | V8 Recall@5 / nDCG@10 |
|---|---:|---:|
| AI/ML engineer | 0.3042 / 0.5354 | 0.3905 / 0.6472 |
| Full-stack developer | 0.2147 / 0.3949 | 0.3194 / 0.5130 |
| Data analyst | 0.2627 / 0.4828 | 0.3438 / 0.5798 |

### B4 decisions by persona

| Persona | Variant | Bid/skip F1 | Scam recall | Injection recall | Errors / 50 |
|---|---|---:|---:|---:|---:|
| AI/ML engineer | V0 | 0.824 | 0.375 | 1.000 | 0 |
| AI/ML engineer | V8 | 0.848 | 0.375 | 1.000 | 1 |
| Full-stack developer | V0 | 0.857 | 0.250 | 1.000 | 2 |
| Full-stack developer | V8 | 0.923 | 0.250 | 0.800 | 1 |
| Data analyst | V0 | 0.889 | 0.286 | 0.800 | 0 |
| Data analyst | V8 | 0.944 | 0.286 | 0.800 | 1 |

### B4 synthetic job types

Accuracy is over completed decisions; model/output errors remain separately shown. Scam/injection detection is calculated on the matching generated type. These small, seeded slices are descriptive. [E06]

| Variant | Job type | Attempts | Errors | Decision accuracy | Detection |
|---|---|---:|---:|---:|---:|
| V0 | Synthetic normal | 116 | 1 | 100/115 (87.0%) | n/a |
| V0 | Scam | 23 | 0 | 23/23 (100%) | 7/23 scam flags (30.4%) |
| V0 | Prompt injection | 11 | 1 | 10/10 (100%) | 9/10 injection flags (90.0%) |
| V8 | Synthetic normal | 116 | 3 | 104/113 (92.0%) | n/a |
| V8 | Scam | 23 | 0 | 23/23 (100%) | 7/23 scam flags (30.4%) |
| V8 | Prompt injection | 11 | 0 | 10/11 (90.9%) | 9/11 injection flags (81.8%) |

### B4 cost and latency provenance

The B5 p95 uses `total_seconds` for successful proposal rows, not retrieval-only latency. Reply-rate denominators are submitted drafts with draft-ID-matched GigSim outcomes. The proposal judge scored 45 V0 and 50 V8 drafts; its mean was 3.00 and 2.94 respectively, but κ=0.000 calibration prevents treating it as calibrated. [E04][E06]

## Appendix C. Part C implementation and remaining work

The graph capabilities below are implementation evidence; the separate R&D C experiment and its limitations are reported in Section 5 and Evidence E13. See the cited code and tests for implementation details. [E12][E13]

| Requirement | Status and evidence |
|---|---|
| C1 bid and conversation graphs | Implemented `StateGraph`: bid analyst/risk/fit run in parallel via `Send`, followed by decision, pricing, writer, verifier, bounded Critic, compliance, and approval. Conversation covers intent, code-owned slots, reply, and approval; scam messages are flagged without drafting. Focused bid/conversation graph tests: 19 passed (12 bid, 7 conversation). |
| C2 state, reducers, and memory | Typed state reducers cover evidence, trace, steps, errors, and status. API/worker memory uses PostgreSQL-backed `AsyncPostgresStore` when `DATABASE_URL` is configured; local/tests without a URL use `InMemoryStore`. Style rules promote only after the same edit recurs in three distinct jobs; outcome stats remain hidden until five results and are keyed by run ID for idempotent updates. Settings lets users delete style rules and outcome summaries. The restart-persistence integration test passed against both configured direct and pooled PostgreSQL endpoints (one pass each). |
| C3 typed hand-offs | Bid and conversation graph state carries Pydantic objects (`JobSpec`, `RiskReport`, `FitReport`, `BidDecision`, `PriceQuote`, `ProposalDraft`, `Critique`, `ComplianceVerdict`, and the corresponding conversation/claim contracts). Nodes validate legacy checkpoint dictionaries at read boundaries; serialization to JSON occurs only for LLM requests, APIs, and human interrupts. The focused graph/API/LLM regression suite passed 61 tests, including runtime assertions that the eight required bid hand-offs remain Pydantic instances across graph execution and checkpoint/resume. |
| C4 critique and budgets | Critic loop is capped at two revisions and tested. Both graphs enforce step and per-thread token budgets. Provider-reported LLM usage is counted; response generation is capped to the remaining allowance, offline heuristic calls use a deterministic estimate, and parallel bid-branch usage is added with a reducer. Token usage survives checkpoint/resume. Exhaustion sets `needs_attention`; run detail exposes the reason and count. Focused token, API visibility, and resume tests pass. |
| C5 approval and edits | Proposal and message graphs interrupt before marketplace writes; the proposal preview is a non-spending `dry_run`. The payload includes the draft, claim evidence, risk, price rationale, compliance result and preview. Approve is refused server-side while blocked; edits are diffed, shown to the user, and re-run through compliance and claim verification; successful edits feed per-user style memory after send. Reject requires a non-empty reason. Per-user `auto_skip_low_fit` only selects skip versus watch and never approves or sends. Focused graph/API tests cover no-write-before-approval, edit/recheck/block, rejection reason validation, message-edit memory, and low-fit autonomy. |
| C6 durable execution | Both real-PostgreSQL integration tests passed: checkpoint crash/resume and API restart with approval through the authenticated API, asserting one submission and one Connects spend. Run history exposes checkpoint IDs and graph nodes; replay validates ownership and branches from the selected checkpoint/node. |
| C7 resilience | Both graphs use configured per-node timeouts and bounded retries for transient errors; cheap LLM nodes have configured fallback models. Marketplace MCP handles bounded transport/429/5xx retries, and pre-write rate limits/outages queue for recovery. Persistent dead letters expose failure reasons via API and run timeline. Post-approval uncertainty is `needs_attention`; write nodes have one attempt to avoid duplicating side effects. The focused C6/C7 suite passed all 35 tests, including both PostgreSQL durability tests. |
| R&D C comparison | Completed: 50 frozen distinct synthetic jobs, 150 paired trials, five counted ReAct/supervisor failures, compiled graph renderings, and scam/approval/Critic/C6 trace links. Aggregate accuracy was 0.34 ReAct, 0.36 supervisor, 0.98 hand-built graph. This is exploratory synthetic evidence; one injection-labeled skip was submitted by ReAct through the benchmark gate. See E13. |

### Viva notes

- **Exactly-once:** submission carries an idempotency key; both PostgreSQL crash-resume and API-restart tests passed with one submission/Connects spend. Replay is available through the authenticated history/replay APIs, not a UI control.
- **Style memory:** a style preference is promoted after the same edit recurs in three distinct jobs; outcome statistics are shown only after five results, and users can delete stored items. PostgreSQL-backed memory survives restart when `DATABASE_URL` is configured; the local/test `InMemoryStore` fallback is volatile.
- **Where a single agent beats the graph:** it did not beat the hand-built graph on accuracy in any measured job-type slice. On ordinary jobs, it also had lower accuracy; on scam/injection jobs both baseline designs scored zero. This is specific to one synthetic, risk-enriched sample and one local model, not a general claim.

[[PAGEBREAK]]

## Appendix D. Evidence register

Every reported measurement or implementation claim above points to one or more entries below. No commit is cited because this workspace is not a Git repository.

| ID | Evidence file(s) | Supports |
|---|---|---|
| E01 | `docs/ARCHITECTURE.md`; `agent/config.yaml`; `agent/graphs/bid_graph.py`; `agent/graphs/conversation_graph.py` | Graph structure, node purposes, current RAG variant, configured graph/token budgets. |
| E02 | `docs/DATA_CARD.md`; `data/processed/kaggle_2024_v1/DATA_MANIFEST.json`; `docs/REPORT_CHECKLIST.md` | Dataset provenance, synthetic labels/outcomes, missing currency, instructor data/hidden-test availability. |
| E03 | `docs/OWN_GIGSIM.md`; `docs/UPWORK_LIVE.md`; `docs/CLIENT_DISCIPLINE.md`; `docs/MCP_TESTING.md`; `docs/TOOLS.md` | Marketplace port, MCP tools, OAuth, approval gates, local simulator and platform limits. |
| E04 | `evals/results/b2/summary.json`; `evals/results/b2/comparison.md`; `docs/RAG_VARIANTS.md`; `docs/RD_B_RESULTS.md` | B2 aggregate/per-persona retrieval, variant comparison, latency and negative reranking result. |
| E05 | `docs/RD_A_RESULTS.md`; `evals/results/rd_a_llm/tasks.json`; `evals/results/rd_a_llm/trials.jsonl`; `evals/results/rd_a_llm/aggregate.json` | R&D A task setup, exact scoring, tokens and results. |
| E06 | `evals/results/b4_exploratory/summary.json`; `evals/results/b4_exploratory/runs.jsonl`; `evals/results/b4_exploratory/judge_proposal_predictions.jsonl`; `evals/results/b4/summary.json`; `evals/reviews/b4/panel.json`; `gigbid-calibration-ratings.json` | B4 sample size/errors, per-persona/type metrics, claims, judge, GigSim rates, latency, cost, full-run/panel status and author labels. |
| E07 | `docs/CLAIM_VERIFICATION.md`; `evals/results/b3/summary.json` | Real-model claim filtering counts, blocked drafts, and verifier limitations. |
| E08 | `docs/OPEN_MODEL_RESULTS.md`; `evals/results/open_model_comparison.json`; `evals/results/open_model_runtime.json` | Model-comparison failures, paired case outcomes, hardware, completion rates and model selection. |
| E09 | `docs/REAL_AGENT_BEHAVIOUR.md`; `evals/results/real_agent_behaviour.json`; `docs/CLIENT_DISCIPLINE.md`; `docs/GIGSIM_WORKFLOW_VERIFICATION.md`; `evals/results/injection_eval.json` | Real-agent fixes/tests, approval behavior, outage recovery, injection controls and known blind spots. |
| E10 | `docs/REPORT_CHECKLIST.md`; `docs/EXTENSION.md` | Unreceived change request, unbuilt extension, and hidden-test/report placeholders. |
| E11 | `docs/RD_B_PREREGISTRATION.md`; `docs/RD_B_ABLATION_RESULTS.md`; `evals/rd_b/ablation_variants.py`; `evals/rd_b/run_ablation.py`; `evals/rd_b/report_ablation.py`; `evals/rd_b/results/ablation_run.json`; `evals/rd_b/results/ablation_per_job.jsonl`; `evals/rd_b/results/ablation_summary.json` | Frozen hypotheses, one-factor conditions, raw paired retrieval measurements, persona/category/safety-type breakdowns, bootstrap intervals, reply-rate interpretation, judge calibration and shipping decision. |
| E12 | `agent/graphs/bid_graph.py`; `agent/graphs/conversation_graph.py`; `agent/resilience.py`; `agent/config.yaml`; `agent/state.py`; `agent/state_conv.py`; `agent/handoffs.py`; `agent/llm.py`; `agent/token_budget.py`; `agent/memory/promotion_rules.py`; `agent/memory/store.py`; `agent/persistence.py`; `agent/runtime.py`; `agent/nodes/learn.py`; `agent/nodes/liaison.py`; `agent/nodes/approval.py`; `agent/nodes/compliance.py`; `agent/nodes/submit.py`; `agent/marketplace_mcp.py`; `apps/api/main.py`; `apps/api/runs.py`; `apps/api/routers/analytics.py`; `apps/api/routers/approvals.py`; `apps/api/routers/runs.py`; `apps/api/routers/settings.py`; `apps/web/src/components/ApprovalPanel.tsx`; `apps/web/src/components/RunTimeline.tsx`; `worker/settings.py`; `tests/conftest.py`; `tests/integration/test_bid_graph.py`; `tests/integration/test_conversation_graph.py`; `tests/integration/test_api.py`; `tests/unit/test_llm_backend.py`; `tests/integration/test_postgres_durability.py`; `tests/integration/test_memory_postgres.py`; `tests/unit/test_memory.py`; `tests/unit/test_degraded_recovery.py`; `tests/unit/test_mcp_client_discipline.py` | Part C graph/state/typed-handoff/memory/approval implementation; C2 PostgreSQL-backed memory restart-persistence test passed against direct and pooled endpoints; C3 Pydantic object hand-offs verified with a 61-test graph/API/LLM regression suite; C4 critic, step/token exhaustion, parallel token aggregation and checkpoint-resume behavior, and visible API/UI failure reasons; C5 human-gated proposal/message writes, non-spending preview, validated decisions, diffed/rechecked edits and style-memory promotion, and skip-only autonomy; C6 checkpoint history/replay plus real-PostgreSQL crash-resume/API-restart/idempotency tests (both passed); C7 timeout/retry/fallback/dead-letter and degraded marketplace recovery (35 focused tests passed). Comparative experiment findings are in E13. |
| E12 | `agent/graphs/bid_graph.py`; `agent/graphs/conversation_graph.py`; `agent/resilience.py`; `agent/config.yaml`; `agent/state.py`; `agent/state_conv.py`; `agent/handoffs.py`; `agent/llm.py`; `agent/token_budget.py`; `agent/memory/promotion_rules.py`; `agent/memory/store.py`; `agent/persistence.py`; `agent/runtime.py`; `agent/nodes/learn.py`; `agent/nodes/liaison.py`; `agent/nodes/approval.py`; `agent/nodes/compliance.py`; `agent/nodes/submit.py`; `agent/marketplace_mcp.py`; `apps/api/main.py`; `apps/api/runs.py`; `apps/api/routers/analytics.py`; `apps/api/routers/approvals.py`; `apps/api/routers/runs.py`; `apps/api/routers/settings.py`; `apps/web/src/components/ApprovalPanel.tsx`; `apps/web/src/components/RunTimeline.tsx`; `worker/settings.py`; `tests/conftest.py`; `tests/integration/test_bid_graph.py`; `tests/integration/test_conversation_graph.py`; `tests/integration/test_api.py`; `tests/unit/test_llm_backend.py`; `tests/integration/test_postgres_durability.py`; `tests/integration/test_memory_postgres.py`; `tests/unit/test_memory.py`; `tests/unit/test_degraded_recovery.py`; `tests/unit/test_mcp_client_discipline.py` | Part C graph/state/typed-handoff/memory/approval implementation; C2 PostgreSQL-backed memory restart-persistence test passed against direct and pooled endpoints; C3 Pydantic object hand-offs verified with a 61-test graph/API/LLM regression suite; C4 critic, step/token exhaustion, parallel token aggregation and checkpoint-resume behavior, and visible API/UI failure reasons; C5 human-gated proposal/message writes, non-spending preview, validated decisions, diffed/rechecked edits and style-memory promotion, and skip-only autonomy; C6 checkpoint history/replay plus real-PostgreSQL crash-resume/API-restart/idempotency tests (both passed); C7 timeout/retry/fallback/dead-letter and degraded marketplace recovery (35 focused tests passed). |
| E13 | `docs/RD_C_PREREGISTRATION.md`; `docs/RD_C_RESULTS.md`; `evals/datasets/rd_c_50.json`; `evals/results/rd_c_comparison.json`; `evals/results/rd_c_trials.jsonl`; `evals/results/rd_c_interrupted_67_trials.jsonl`; `evals/results/rd_c_initial_pilot.jsonl`; `evals/results/rd_c_graphs/`; `evals/results/rd_c_traces/`; `evals/runners/rd_c_comparison.py`; `tests/unit/test_rd_c_comparison.py`; `tests/integration/test_postgres_durability.py` | Preregistered matched 150-trial architecture comparison, raw and excluded interrupted attempts, aggregate/persona/job-type results, five counted failures, synthetic simulator limitations, compiled graph renderings, required traces, and C6 durability-test reference. |

