# B3 — Claim verification before the Critic

B3 is implemented: proposals are split into sentence-level claims, checked against retrieved evidence, and filtered before the Critic receives the draft. Unsupported **and partly supported** claims are removed. No automatic rewrite invents a replacement fact. Empty drafts remain blocked by the existing Critic/compliance/approval gates.

## Real-model before/after measurement

Twelve ordinary synthetic development jobs, four per persona, were drafted with the configured local Qwen model. Jobs and evidence were fetched through official SDK MCP clients; the actual Writer, Verifier and Critic node functions were executed in that order. No proposals were submitted. The same twelve development jobs were reused while fixing defects, so this is an iterative development measurement, not an unbiased held-out test.

| Persona | Drafts | Sentence units before / after | Unsupported before | Before rate | Unsupported after repeat check | After rate | Empty cleaned drafts |
|---|---:|---:|---:|---:|---:|---:|---:|
| ai-ml-engineer | 4 | 12 / 4 | 3 | 25.0% | 0 | 0.0% | 1 |
| fullstack-dev | 4 | 12 / 6 | 3 | 25.0% | 0 | 0.0% | 1 |
| data-analyst | 4 | 19 / 12 | 0 | 0.0% | 0 | 0.0% | 0 |
| All | 12 | 43 / 22 | 6 | 14.0% | 0 | 0.0% | 2 |

Unsupported sentence units per proposal: **0.500 before**, **0.000 after**. Partly supported units before filtering: **14**. Claim retention: **51.2%**.

Rates count normalized cover-letter and screening-answer sentence units, including nonfactual boilerplate. A missing citation/quote can cause an unsupported label; this rate is not a human-measured hallucination rate. Zero retained claims yields an undefined after-rate, reported as n/a, not a misleading 0%. A low unsupported count obtained by deleting useful text does not demonstrate good proposal quality.

## Verification behavior

- Compound claims are split on sentence boundaries, newlines and semicolons. Citation IDs, claim kind and screening section are preserved.
- Experience hidden under a boilerplate label is still checked. Model-authored logistics are removed upstream; actual calendar logistics retain the existing code-built path.
- Missing/unknown citations cannot fall back to arbitrary evidence. One cited source must establish each factual claim; unrelated evidence fragments are not concatenated into apparent support.
- Deterministic guards reject fabricated whole numbers/percentages, absent named organizations, unestablished qualification levels and extra accomplishments. These conservative rules can also reject valid paraphrases.
- With `verification.backend=auto`, a real `OpenAICompatLLM` additionally runs the semantic prompt. The schema requires a real citation ID and an exact source passage for supported/partly supported decisions. Claim indices and source IDs/passages are constrained to supplied values. Missing/duplicate verdicts or invalid quotes fail closed.
- Survivors are checked again and any downgraded claims are removed before Critic. The graph already routes Writer → Verifier → Critic; every revision repeats verification.
- Human-edited cover letters are rechecked before approval and blocked when unsupported; a separate edited-cover field cannot override the filtered claim list.
- `rules` is the explicitly labeled offline verifier. `llm` forces semantic checks. In `auto`, offline test doubles use rules; real-model checks never silently fall back after a model failure. The verifier inherits the configured Writer model unless a `claim_verifier` model is configured in the active profile.

## Synthetic controls and pilot failures

Controls are authored, deliberately injected examples with labels established by construction, not human annotation or judge calibration. They are excluded from the natural-draft rates above.

| Control | Expected | Observed |
|---|---|---|
| exact supported fact | supported | supported |
| fabricated number | unsupported | unsupported |
| unknown citation | unsupported | unsupported |
| substring number | unsupported | unsupported |
| invented employer | unsupported | unsupported |
| unsupported extra action | partly_supported | partly_supported |

The initial pilot found a semantic verdict that changed on a repeat check. A subsequent positive control exposed optional citation/quote schema fields: the small model omitted those fields, causing even a valid source sentence to be rejected. Survivor rechecking and mandatory source fields address those concrete defects. Both pilot artifacts are retained under `evals/results/b3/pilot/`; failed runs are not presented as successful final measurements.

## Limits and reproduction

The verifier is evidence-conditioned, not an independent fact checker. Source authorship/outcomes may be user-reported or synthetic. The Writer and semantic checker use the same small model; repeat agreement is not independent human ground truth, and exact quotes alone do not prove entailment. Semantic labels remain uncalibrated. B4's 30 author labels are measured against the judge (11/30 agreement; Cohen's kappa 0.000), which shows no agreement beyond chance; its scores are not calibrated. The full B4 outcome evaluation remains paused at 16/1,200 runs. The separate exploratory sample completed 300 attempts (295 decisions, five model/output errors); all 95 eligible proposals were rubric-scored, but the blind classmate panel has no ratings yet. This sample is exploratory, not full B4 completion. Extra verification calls add latency/token use; every returned provider usage object for this run is saved in the summary.

```bash
python -m evals.rd_b.verify_claims_real
python -m evals.rd_b.report_claims
```

Evidence: [per-draft text, retrieved evidence and verdicts](../evals/results/b3/proposals.jsonl), [metrics, controls and raw model responses/usage](../evals/results/b3/summary.json), [test evidence](../evals/results/b3_validation.json).

Code: `rag/verify.py`, `agent/nodes/verifier.py`, `agent/nodes/compliance.py`, `agent/prompts/claim_verifier.md`; regressions in `tests/unit/test_b3_verification.py`.
