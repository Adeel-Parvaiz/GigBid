# R&D A — Does tool granularity change agent behaviour?

Executed 40 paired tasks under each of three conditions: **120 actual LLM calls** to `qwen25-15b` (Qwen2.5 1.5B, local llama.cpp). The model selects the tool **and generates its arguments**; the evaluator executes that choice through official SDK MCP sessions. This replaces the earlier description-only BM25 baseline, which remains archived under `evals/rd_a/results/`.

| Condition | Tool-selection accuracy | Argument accuracy | Successful task result | Mean input tokens | Mean output tokens | Mean total tokens/task |
|---|---:|---:|---:|---:|---:|---:|
| 15 fine-grained tools | 95.0% | 82.5% | 90.0% | 2585.4 | 46.0 | 2631.4 |
| 3 combined tools | 30.0% | 15.0% | 15.0% | 2633.4 | 53.5 | 2686.9 |
| Best set (fine) with rewritten descriptions | 90.0% | 75.0% | 87.5% | 2763.4 | 45.0 | 2808.5 |

On these tasks, fine-grained tool selection was +65.0 percentage points relative to the combined tools. Rewritten descriptions changed selection by -5.0 percentage points relative to the selected base. These are measured differences for this model and authored task set; they do not establish a general ranking for other models.

## What changed

- Fine: all 15 real Portfolio, Marketplace and Workspace tools, using production names, descriptions and input schemas.
- Coarse: three actual MCP tools (`portfolio_operations`, `marketplace_operations`, `workspace_operations`). Each accepts an enumerated operation plus its argument object and dispatches through the original MCP session. All original argument contracts are included in the catalog, so capabilities are retained.
- Rewritten: choose the better fine/coarse set by selection accuracy, then argument accuracy, then lower token use; rewrite descriptions while retaining that set's names, schemas and behavior. Rewrites are fixed in code, not tuned to individual failures.

## Tasks, scoring and token accounting

The same 40 curated tasks cover all 15 operations: evidence search/fetch/skills, job search/fetch, client history, Connects, threads/messages, draft previews, approved fixture submissions/messages, slots, tentative holds and unsent email. Each has a known correct operation, exact input values and a result assertion. Previously implicit amounts, request keys, text, dates and limits are stated explicitly in the revised task requests. Gold tool names and argument objects are never sent to the selector. Tool order is shuffled using the same task-specific seed in each condition.

- Tool selection: correct named tool; combined tools must also select the correct inner operation. Choosing the right server alone does not pass.
- Argument accuracy: correct selection plus exact structured argument equality after recursively expanding declared defaults. Omitting a default-valued field is accepted; wrong identifiers, missing requested nondefault limits or changed text are failures. This deliberately avoids a subjective semantic judge.
- Successful result: correct selection, successful MCP execution and the task's result assertion. Schema validity is also recorded separately.
- Tokens: actual provider `usage.prompt_tokens + usage.completion_tokens` for each task. Includes the complete catalog and request. No token estimates, heuristic calls or semantic repair attempts. One recorded model response and at most one selected tool invocation per task; a combined invocation additionally makes its internal MCP dispatch.

Temperature: 0; seed: 4016; maximum output: 600 tokens; JSON-object response format. Raw responses, selected arguments, gold answers, token usage, timing, errors and catalog hashes are retained. The interrupted run resumed from its 90 recorded responses; completed calls were not repeated. Timed-out requests without a returned usage object may have consumed additional tokens; those unknown interrupted-request tokens are excluded from the completed-trial means. Saved responses were scored consistently with recursive default normalization.

## Limits

One model, one sample per task/condition, fixed condition order and a curated synthetic task set. The best set is selected and re-evaluated on these same tasks, so rewritten results are exploratory rather than an independent held-out evaluation. Schema size and routing structure both change in the combined condition. The selector is a dedicated real-model tool-calling harness, not evidence that production graph routing changed; production currently uses explicit role allowlists. Inference runs locally without a billed API; this report compares tokens, not an invented dollar cost. All mutations are isolated sample fixtures; there are no real marketplace, calendar or email writes.

## Submission evidence

- [Tool inventory and trust rationales](TOOLS.md): one row per exposed project tool, plus third-party tools and experimental wrappers.
- [A7 passing protocol tests, schema gate and official Inspector screenshots](MCP_TESTING.md).
- [Single real-agent grounded GigSim proposal](../evals/results/single_grounded_proposal.md), [source evidence, MCP preview and actual model usage](../evals/results/single_grounded_proposal.json). The single drafting agent reads jobs/evidence only through MCP, generates a future plan, selects source IDs, and renders past-work claims as verified exact portfolio quotations. Preview only; no Connects spent.
- [40 revised task specifications](../evals/results/rd_a_llm/tasks.json), [120 raw trials](../evals/results/rd_a_llm/trials.jsonl), [aggregate metrics](../evals/results/rd_a_llm/aggregate.json), [regression results](../evals/results/rd_a_validation.json).

Reproduce against the documented local model endpoint:

```bash
python -m evals.rd_a.llm_experiment --model qwen25-15b
# To resume an interrupted run without repeating saved calls:
python -m evals.rd_a.llm_experiment --model qwen25-15b --resume
python -m evals.runners.single_grounded_proposal
python -m evals.rd_a.report_llm
```
