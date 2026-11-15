# A6: MCP client discipline

A6 is implemented and verified against an actual marketplace process outage. The three areas are role-scoped tools, bounded failures, and safe automatic recovery.

## Tool access

`agent/mcp_client.py::ALLOWLIST` filters tool names per role before tool discovery or invocation. Unknown roles and an explicitly empty allowlist deny everything. Scout can only search jobs; job loading reads job/client details; Pricing reads Connects; Liaison reads conversations; the calendar role reads free slots; Fit Matcher reads portfolio evidence. Writer/Verifier/Critic have only their declared evidence tools. External writes belong to the approval gate. The separate preview role can call proposal creation only with `dry_run=true`, enforced in the client rather than left as a naming convention.

Every write or preview requires a valid idempotency key. Duplicate advertised tool names are rejected rather than silently selecting a server. Live Upwork has action-specific mappings and two human gates; GitHub has its own three-tool read allowlist and official-server read-only flag. These do not expose a general-purpose unrestricted MCP client to model-authored tool names.

## Timeouts and retries

The common MCP client defaults to 15 seconds per attempt and two retries. Discovery and read invocation each have a bounded attempt budget, with exponential delays of 0.3 and 0.6 seconds between attempts. There is no sleep after the last failure. Constructor validation caps retries at five. These are per-phase limits, not a claim that the whole discovery-plus-call always finishes in 15 seconds.

Transport failures, including nested AnyIO exception groups, connection errors, timeouts and transient HTTP statuses, are recognized. Authentication, schema failures and tool execution errors fail without transport retries. Mutating calls get one automatic attempt even if the server claims idempotency; dry-run previews can use read-style retries. A failure after a write requires review, not automatic resubmission. Cached tool definitions are invalidated after transport exhaustion so the next request can rediscover the recovered server.

Unit tests cover the complete deny matrix, explicit empty policy, preview restrictions, nested transport failures, exact backoff/attempt counts, timeout exhaustion, tool-error no-retry behavior, duplicate tool names and single-attempt writes.

## Degraded mode and recovery

Read-stage marketplace outages persist a run as `queued_degraded` and emit that same status over SSE. This includes initial job loading and later reads such as the balance check during pricing. The API recovery loop checks at five-second intervals by default (`DEGRADED_RECOVERY_INTERVAL`), processes at most four queued records per cycle and runs only records owned by that process origin. The worker also checks its own queued records during its scheduled scouting cycle.

Recovery verifies the original application user and marketplace connection binding. It refuses records with an existing approval, submission, send result or pending human interrupt. A changed connection or a record that might have crossed a write gate becomes `needs_attention`. Once the marketplace is reachable, a read checkpoint resumes or a fresh analysis supersedes the failed initial attempt. Either route still stops at normal human approval. Recovery never silently approves or executes an external write.

The web UI shows the outage and queued count. When health recovers it clears the banner and reloads the inbox automatically, without needing Try again. Authenticated health checks use that user's selected marketplace; public health checks use the configured fallback. The local outage test does not exercise a live Upwork outage.

## Measured evidence

The isolated Chromium test starts the real project GigSim REST service and authenticated Marketplace MCP server. It kills the MCP process with SIGKILL, queues an analysis through the actual API, then starts a new MCP process on the same endpoint. No outage response is mocked.

| Stage | Connects | Submitted proposals |
|---|---:|---:|
| Initially healthy | 100 | 0 |
| MCP killed; work queued | 100 | 0 |
| Automatically recovered; waiting for approval | 100 | 0 |
| After browser Approve | 92 | 1 |

The upstream simulator database persists while MCP is restarted. This experiment uses synthetic data and HeuristicLLM to isolate transport and recovery behavior; it is not an LLM-quality or real marketplace-outcome benchmark. The test-only kill/start endpoints exist only in `evals.runners.a6_fixture_api`, not in the production application.

Evidence:

- [Outage with queued work](../evals/results/a6/01-marketplace-down-queued.png)
- [Recovered proposal still requiring approval](../evals/results/a6/02-recovered-awaiting-approval.png)
- [Observed balances and process replacement](../evals/results/a6/observations.json)
- [Actual process/browser test result](../evals/results/client_discipline_browser.json)
- [Python regression output](../evals/results/client_discipline_tests.json)

Reproduce in the configured WSL checkout:

```bash
python -m pytest -q
python -m scripts.run_frontend_tests --config=playwright.a6.config.ts
```

The full Python suite passed 143 tests with two infrastructure skips. The separate general Chromium suite has ten passing tests. The actual-kill recovery test is an additional passing case. Isolated test services are stopped afterward; the user's normal frontend/backend and account connections are not targets of this fault test. Postgres/Redis service checks remain separate infrastructure skips.
