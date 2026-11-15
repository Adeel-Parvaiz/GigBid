# Architecture

State vs trace vs memory (kept apart on purpose):
- **State** (`agent/state.py`): what this job needs right now. Typed, with reducers where parallel branches write (`evidence`, `trace`, `steps`, `errors`, `tokens_used`, `status`).
- **Inter-agent contracts** (`agent/handoffs.py`): decision-bearing bid and conversation outputs stay as Pydantic models in graph state; they are serialized to JSON only at LLM, API, and human-interrupt boundaries.
- **Execution trace**: `trace` list per node (name, ms, keys written) plus checkpoint history for replay. Audit only; decisions never read it. Authenticated run APIs expose history and allow replay from a run-owned checkpoint at a selected graph node.
- **Long-term memory** (`agent/memory`): only promoted items. API and worker use the shared PostgreSQL-backed LangGraph store when `DATABASE_URL` is configured; local/tests without a URL use `InMemoryStore`. Style rules need the same edit signal in 3 distinct jobs; outcome stats stay hidden below 5 results and are idempotent by run ID. Raw tool output never enters memory. Users can view and delete style rules and outcome summaries in Settings.

## Why each agent exists
| Node | Why | Model |
|---|---|---|
| load_job | one place that reads marketplace data (job, client history) | none |
| analyst | structured JobSpec | small |
| risk | scams, free work, off-platform asks, injection. **Rule floor + LLM that can only add risk** | small |
| fit_matcher | requirement→evidence mapping via Portfolio MCP; runs parallel with analyst so it works from the raw job | none (retrieval) |
| decide | bid/watch/skip from config thresholds; deterministic so it is explainable | none |
| pricing | bid from client budget, user floor, Connects affordability | none |
| writer | claims, each with evidence ids | strongest |
| verifier | splits into claims, checks each against evidence, drops unsupported **before** the critic | lexical stand-in |
| critic | grounding, personalisation, length; max 2 sends back | strongest |
| compliance | policy rules from config: scrub contacts, drop guarantees, block off-platform | none |
| approval | `interrupt()`; payload = draft, per-claim evidence, risk, price, dry-run | human |
| submit / send | only after approve; idempotency key makes retries safe | none |

Deterministic nodes are deliberate: where a rule is enough, an LLM adds cost and a way to be talked out of it.
Whether the multi-agent split beats one ReAct agent is R&D question C and is **not measured yet**.

Both graphs enforce per-thread step and token limits. The LLM adapter caps each provider response to the remaining token allowance and records provider-reported usage; the offline heuristic backend records a deterministic estimate. Usage is reduced across parallel bid branches and retained in checkpoints. Exhaustion stops downstream work with `needs_attention`; the run detail API and progress panel show the reason and token count.

## Safety properties (each has a test)
Every proposal and message pauses at a human `interrupt()` before any write; proposal previews use the separate `dry_run=true` allowlist, so they create no draft and spend no Connects. Approval is checked server-side, including blocked-draft refusal. Edits are unified-diffed, shown in the approval panel, and re-checked by Compliance (including grounding for new claims); successful edits feed user-scoped style memory after send. Reject decisions require a non-empty reason. Per-user autonomy can turn low-fit skip into `watch`, but cannot approve or send. LLM cannot lower a rule-based risk score; logistics sentences (calendar slots) are written by code, never by the model; tenant scoping applies to every run query; MCP tool errors raise instead of looking like data.

## Durability and failure recovery

The configured LangGraph checkpointer stores job/thread checkpoints in PostgreSQL; run metadata and dead-letter reasons are kept in the API RunStore. After restart, pending approval is reconstructed from the checkpoint. The history endpoint returns checkpoint IDs and available graph nodes; replay validates that the checkpoint belongs to the run and branches to the selected node. Mutating marketplace nodes are not automatically retried; idempotency keys protect submission replay.

Both graphs apply configured per-node timeouts and bounded retries to transient transport, timeout, rate-limit, and selected 5xx failures. Cheap LLM nodes can use configured fallback models. The marketplace MCP client handles bounded request retries; pre-write rate limits/outages enter `queued_degraded` for recovery. Irrecoverable pre-write failures enter a persistent, user-visible `dead_letter`; failures after approval or a possible write enter `needs_attention` because the external outcome may be uncertain.
