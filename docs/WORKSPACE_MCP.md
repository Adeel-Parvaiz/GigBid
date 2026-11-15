# A3: Workspace MCP

The Workspace server uses the official MCP Python SDK. Its backing is the local mock permitted by A3. The application defaults to `McpWorkspace`, not direct `WorkspaceService` calls. Mock data and SQLite access remain inside the server. The three tools declare input constraints, output schemas and MCP annotations:

| Tool | Owner | Effect | Annotation | Allowed agent |
|---|---|---|---|---|
| `get_free_slots` | Workspace MCP / local calendar mock | Read working-day interview slots | read-only, idempotent | `liaison_calendar` |
| `create_tentative_hold` | Workspace MCP / local calendar mock | Create a tentative hold, never a confirmed invitation | write, non-destructive, idempotent | `approval_gate` |
| `create_email_draft` | Workspace MCP / local mail mock | Save an unsent draft; never send mail | write, non-destructive, idempotent | `approval_gate` |

The calendar role cannot call write tools. The conversation graph obtains free slots through MCP before approval and creates its tentative hold through MCP only after approval. The email draft capability is exposed and tested over MCP; the conversation graph does not automatically create an email for every interview.

Default transport is stdio using the same Python interpreter as the application. `python -m scripts.run_dataset` and `python -m scripts.run_gigsim --with-api` therefore need no separate Workspace daemon. Workspace server processes share persistent mock state; the GigSim launcher uses ignored `.local-models/gigsim/workspace.sqlite`. Otherwise the default path is `.local-models/workspace/state.sqlite`. Override `WORKSPACE_DB` to isolate runs. Never point tests at an account's real local state.

For a dedicated HTTP server:

```bash
python -m mcp_servers.workspace.server streamable-http
# application environment:
export GIGBID__workspace__source=mcp
export GIGBID__workspace__transport=streamable_http
export GIGBID__workspace__url=http://127.0.0.1:8002/mcp
```

The HTTP server binds to loopback by default. Docker Compose uses HTTP on its internal network and persists workspace state on a volume. These mock endpoints have no bearer authentication; do not expose them publicly. No Google credentials or paid APIs are required, and no actual email is sent. Dates/times are local mock calendar values; this is not a synchronized Google account.

Application construction rejects `workspace.source=local`. Unit fixtures and the older diagnostic harness that inspects mock internals must explicitly inject a workspace double in Python; no configuration switch silently enables direct mock access. Normal application defaults, the shipped GigSim launcher and the main real-model HTTP workflow verifier select MCP.

Tests cover all three tools through real stdio MCP, persisted state across fresh processes/clients, idempotent retries and changed-payload rejection, tool allowlists, HTTP MCP and the actual conversation graph's approval gate. Workspace input/output schemas and annotations have a contract snapshot. Run `python -m pytest -q tests/integration/test_workspace_stdio.py tests/integration/test_workspace_over_mcp.py tests/contract/test_tool_schemas.py`.

Verified results: **119 Python tests passed, 2 infrastructure skips; 8 Chromium tests passed; 27 real-model application workflow checks passed**. The real HTTP application used Workspace MCP to offer three slots, reached an interrupt without creating a hold, restored that approval after an abrupt restart, then created exactly one tentative hold after approval. The hold persisted after another restart. The stdio integration test separately creates an unsent email draft, recreates the client/server process and confirms idempotent replay. See `evals/results/workspace_mcp_tests.json`, `workspace_mcp_playwright.json` and `gigsim_workflow/results.json`.

The initial real workflow caught a missing stdio environment mapping for `WORKSPACE_DB`; it is fixed and protected by a regression assertion that the requested database is actually created. The initial result remains in `evals/results/workspace_mcp_workflow_initial.json`. All isolated workflow services were stopped after verification. A3 is implemented with the permitted local mock; this does not complete live Upwork or GitHub integration.
