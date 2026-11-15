# R&D Question C: preregistration

## Question and hypothesis

Does the hand-built GigBid graph justify its added orchestration cost compared with one
tool-using ReAct agent and the `langgraph-supervisor` prebuilt supervisor?

Before running the comparison, the hypothesis is: the hand-built graph will make fewer
unsupported factual claims and route more scam/injection jobs to skip than the single
ReAct agent, while using more tokens and taking longer. The supervisor is expected to
fall between them overall. The ReAct agent may be more accurate or cheaper on ordinary
jobs that need little coordination.

## Frozen sample

Use the 50-job sample in `evals/datasets/rd_c_50.json`, selected before any model run
from the three synthetic 200-job persona dev sets. The sample has 17 AI/ML-engineer,
17 data-analyst, and 16 full-stack jobs. It contains 18 ordinary bids, 12 ordinary
skips, 10 scam jobs, and 10 prompt-injection jobs (each persona contributes six
ordinary bids and four ordinary skips). All 50 job IDs are distinct. Selection is
deterministic using seed 4016 and a SHA-256 ordering within each stratum; cross-persona
duplicate IDs are skipped and the next distinct job in that stratum is used.

All three variants receive the same job IDs, persona profile, portfolio corpus,
retrieval configuration, model endpoint/model, and per-job graph/token budgets. The
run order is fixed by the saved sample and variant list. The model endpoint is local;
the resolved model name is saved in result metadata.

## Variants

1. One `create_react_agent` with the project marketplace, evidence, and pricing tools.
   Mutating tools reject calls unless the external approval harness authorizes them.
2. The prebuilt `langgraph-supervisor` supervisor coordinating separate research and
   proposal agents with the same tool surface and guarded writes.
3. GigBid's hand-built bid `StateGraph`, including parallel analyst/risk/fit work,
   decision, pricing, writing, claim verification, critic, compliance, approval, and
   submission.

The common post-run evaluator checks every raw proposal with the same deterministic
claim verifier and compliance rules. A benchmark-only approval harness submits only
eligible drafts to the project's local GigSim. This is an isolated simulator action,
not a human approval and never a real marketplace write.

## Measures

- **Bid-or-skip accuracy:** exact accuracy against synthetic `gold_action`; `watch` is
  counted as skip. Failed runs count as incorrect.
- **Unsupported claims:** unsupported factual sentences per raw proposal, measured by
  the same rule-based evidence checker for all variants; also retain the graph's
  internal before/after verifier counts.
- **Compliance:** count policy-rule violations found in raw drafts and the fraction
  blocked or scrubbed before simulator submission. Since the same final guard is
  applied to every variant, distinguish violation incidence from guard catch rate.
- **GigSim reply rate:** replies divided by submitted eligible proposals, as returned
  by the project-owned synthetic rule-based client model. This is not a real reply or
  hiring rate.
- **Tokens and latency:** model-reported total tokens and wall-clock seconds per job;
  include architecture calls, but not deterministic post-run scoring. Missing provider
  usage remains explicitly missing rather than being presented as measured.
- **Breakdowns:** report by persona and by ordinary/scam/injection class. The small,
  deliberately risk-enriched sample is exploratory; no significance claim is made.

## Protocol amendment after harness smoke run

Before the complete 150-trial run, a 19-row harness smoke run recorded three truncated model outputs
under a 512-token per-call completion limit: two final recommendation responses and one hand-built
graph `JobSpec`. The raw rows are retained at `evals/results/rd_c_initial_pilot.jsonl` and excluded
from all comparison aggregates. A follow-up one-job smoke run under a 1,024-token cap still found a
truncated ReAct recommendation and a supervisor response that exceeded text-field limits; the
hand-built graph completed (`evals/results/rd_c_cap_smoke_1024_validation.json`). A one-job run at
2,048 tokens eliminated truncation but showed that the supervisor can exceed strict claim/evidence
list counts (`evals/results/rd_c_cap_smoke_2048_validation.json`). The complete run uses the same
2,048-token per-call completion cap for all three variants and the same 12,000-token per-job limit.
Conciseness remains an instruction, not a validation-based exclusion: valid verbose model output is
preserved for common evaluation. The final schema smoke is retained in
`evals/results/rd_c_cap_smoke.json` and excluded from aggregate comparison. These amendments are
disclosed because they followed smoke runs; the frozen sample and hypotheses are unchanged.

A subsequent comparison attempt stopped after 67/150 trial rows, before simulator outcomes or
aggregates were finalized. It is retained as `evals/results/rd_c_interrupted_67_trials.jsonl` and
excluded from the final paired results; the complete run is restarted from the frozen sample.

## Failure and exclusion policy

Do not replace, retry, or remove a job because its output is poor. Record runtime/model
errors as failed trials and count them as incorrect. Do not apply a post-hoc JSON repair
or retry failed generation. Do not silently substitute a different model. If the required
local model or a comparative dependency is unavailable, stop before the 150 trials and
report the blocker rather than substituting a heuristic double.
