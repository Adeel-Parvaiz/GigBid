# A7 — MCP tests and Inspector evidence

A7 is implemented and locally verified. The full Python suite passed **149 tests**, with **2 infrastructure skips** (Postgres/Redis) and 14 dependency deprecation warnings. CI-mode snapshot protection was enabled during this run. See `evals/results/mcp_a7_tests.json` and `evals/results/mcp_a7_junit.xml`. GitHub Actions is configured to execute the suite and upload JUnit results; an external Actions run is not claimed.

## Official SDK in-memory client

`tests/unit/test_mcp_inmemory.py` uses `mcp.shared.memory.create_connected_server_and_client_session`. Requests travel through MCP serialization, schema validation and the server session rather than calling tool functions directly.

| Server | Verified behavior |
|---|---|
| Portfolio | All three tools; evidence attribution fields; both resource templates and resource reads; prompt discovery and rendering; invalid input and cross-owner rejection |
| Marketplace | All nine tools; dry-run has no mutation; draft and submission; repeated submission spends Connects once; messages; repeated message sends once; invalid bid rejection |
| Workspace | All three tools; free slots; tentative holds; unsent email drafts; idempotent repeats; invalid date/key rejection |

All mutation checks use disposable local fixtures. They do not contact Upwork, GitHub, Google or email recipients.

## Signature gate

`tests/contract/test_tool_schemas.py` compares input schemas, output schemas and annotations against three checked-in baselines in `tests/contract/snapshots/`. This covers all 15 project tools. Missing snapshots fail instead of silently creating a new baseline. Regression tests prove that changed signatures fail and CI cannot regenerate snapshots. Descriptions remain intentionally outside the snapshot because the separate R&D A experiment rewrites them.

Run the focused eight checks:

```bash
CI=true python -m pytest -q tests/unit/test_mcp_inmemory.py tests/contract/test_tool_schemas.py
```

For a deliberate API change, unset `CI`, regenerate only the affected server snapshot, review its diff, then rerun without update mode:

```bash
UPDATE_SNAPSHOTS=1 python -m pytest -q tests/contract/test_tool_schemas.py::test_marketplace_signatures_are_stable
python -m pytest -q tests/contract/test_tool_schemas.py
```

## Actual MCP Inspector captures

The official `@modelcontextprotocol/inspector@2.15.0` web application was installed from npm. Chromium drove its real connection and execution screens. The captures show connected status, available tools, annotations, successful `tools/call` protocol messages and structured output:

- [Portfolio — list_skills](../evals/results/inspector/01-portfolio.png)
- [Marketplace — get_connects_balance](../evals/results/inspector/02-marketplace.png)
- [Workspace — get_free_slots](../evals/results/inspector/03-workspace.png)

`evals/results/inspector/observations.json` records capture time and fixture scope. Adjacent text exports are the visible page text. These are Inspector screenshots, not reconstructed UI or GigBid application screenshots. Portfolio and Workspace use stdio; Marketplace uses authenticated Streamable HTTP. The catalog, bearer token, audit log and workspace database are disposable. Inspector authentication remains enabled. No real account connection is needed.

To reproduce from an activated Linux/WSL environment with Node 22, the project's Python dependencies and `apps/web` npm dependencies installed:

```bash
npm install --prefix .local-models/mcp-inspector --no-audit --no-fund @modelcontextprotocol/inspector@2.15.0
cd apps/web
npx playwright install --with-deps chromium
cd ../..
python -m scripts.capture_mcp_inspector
```

The runner starts only its isolated servers, captures all three calls, and stops its process groups afterward. It refuses occupied fixture ports 16274, 16275, 16278 and 16281. Use `--node /absolute/path/to/node` when Node is not on PATH; existing Playwright cache/library environment settings are honored. Screenshots are written to `evals/results/inspector/`.

This completes A7's testing deliverables. The separate 40-task tool-granularity R&D experiment and any unverified third-party account actions are not implied by these fixture tests.
