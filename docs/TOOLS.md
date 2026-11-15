# Tools (one row per tool)

A7 protocol tests, signature snapshots and official Inspector screenshots: [MCP testing evidence](MCP_TESTING.md).

Portfolio search additionally accepts a validated B2 retrieval-layer filter; stdio server model configuration is forwarded explicitly. V0/V1/V2/V3/V8 stay behind the same read-only tools: [variant details](RAG_VARIANTS.md).

| Tool | Server | R/W | Annotations | Auth |
|---|---|---|---|---|
| search_evidence | portfolio | read | readOnly, idempotent | none (stdio) / bind to one freelancer via `PORTFOLIO_FREELANCER_ID` |
| get_case_study | portfolio | read | readOnly, idempotent | same |
| list_skills | portfolio | read | readOnly, idempotent | same |
| search_jobs | marketplace | read | readOnly=true, destructive=false, idempotent=true, openWorld=true | bearer token -> user, per-user rate limit |
| get_job | marketplace | read | readOnly=true, destructive=false, idempotent=true, openWorld=true | bearer token -> user, per-user rate limit |
| get_client_history | marketplace | read | readOnly=true, destructive=false, idempotent=true, openWorld=true | bearer token -> user, per-user rate limit |
| get_connects_balance | marketplace | read | readOnly=true, destructive=false, idempotent=true, openWorld=true | bearer token -> user, per-user rate limit |
| list_threads | marketplace | read | readOnly=true, destructive=false, idempotent=true, openWorld=true | bearer token -> user, per-user rate limit |
| list_messages | marketplace | read | readOnly=true, destructive=false, idempotent=true, openWorld=true | bearer token -> user, per-user rate limit |
| create_proposal_draft (dry_run flag) | marketplace | write (draft) | not destructive, idempotent, openWorld | bearer; idempotency key required |
| submit_proposal | marketplace | write | **destructive**, idempotent (key), openWorld | bearer; idempotency key required |
| send_message | marketplace | write | **destructive**, idempotent (key), openWorld | bearer; idempotency key required |
| get_free_slots | workspace (local calendar mock) | read | readOnly, non-destructive, idempotent | local stdio; HTTP loopback/internal network |
| create_tentative_hold | workspace (local calendar mock) | write (tentative only) | not destructive, idempotent | same; approval_gate allowlist |
| create_email_draft | workspace (local mail mock) | write (unsent draft only) | not destructive, idempotent | same; approval_gate allowlist |
| upwork__list_accounts | official Upwork | read (account discovery) | provider annotations; read allowlist | per-user OAuth/PKCE, encrypted tokens |
| upwork__find_jobs | official Upwork | read (search/get) | provider annotations; read action allowlist | same |
| upwork__get_profile | official Upwork | read (Connects balance) | provider annotations; read action allowlist | same |
| upwork__get_messages | official Upwork | read (rooms/messages) | provider annotations; read action allowlist | same |
| upwork__list_freelancer_proposals | official Upwork | read (duplicate/preflight check) | provider annotations; read allowlist | same |
| upwork__manage_proposals | official Upwork | write (approved preview action only) | provider declares a mixed-action tool; runtime restricts to validated preview | same; first human gate |
| upwork__confirm_preview | official Upwork | write (platform confirmation) | provider annotations; explicit execution gate, no automatic retry | same; second explicit human gate |
| upwork__send_message | official Upwork | write (platform send) | provider annotations; locally staged draft, no automatic retry | same; second explicit human gate |
| get_me | official GitHub MCP v2.1.0 | read | readOnly; server additionally runs --read-only | per-user OAuth session in official server memory |
| get_file_contents | official GitHub MCP v2.1.0 | read | readOnly; client allowlist + schema validation | same; README imports require owner/authorship confirmation |
| search_repositories | official GitHub MCP v2.1.0 | read | readOnly; client allowlist + schema validation | same; public repositories |
| portfolio_operations | R&D-only combined Portfolio MCP | read | unspecified; conservative MCP host defaults | isolated SDK in-memory session |
| marketplace_operations | R&D-only combined Marketplace MCP | read/write (sample fixtures only) | unspecified; conservative MCP host defaults | isolated SDK in-memory session; explicit task authorization |
| workspace_operations | R&D-only combined Workspace MCP | read/write (local mock only) | unspecified; conservative MCP host defaults | isolated SDK in-memory session; explicit task authorization |

Per-agent allowlists: `agent/mcp_client.py::ALLOWLIST` (write tools only for the `approval_gate` role, used after a human approved).
The `approval_preview` exception is enforced as dry-run-only. A6 now includes bounded discovery/read retries, no automatic write retry, persistent queued-read recovery and a real process-kill Chromium check; see `docs/CLIENT_DISCIPLINE.md`.
Upwork trust rationale: use Upwork's own hosted MCP endpoint and account authorization; validate discovered schemas and permit only read tools and draft operations with a separate platform confirmation. See `docs/UPWORK_LIVE.md` for tested scope and remaining account verification.
GitHub trust rationale: use GitHub's official checksum-verified server for repository reads, disable writes at the server and client, and treat imported README text as untrusted attributed evidence rather than instructions or verified outcomes. See `docs/GITHUB_MCP.md`.
Audit log: marketplace server, append-only JSONL, PII-masked, with user and trace id.
The Upwork rows list the mapped adapter capabilities and authorization preflight tools, not all tools advertised upstream. The discovered catalog was validated at connection time; unmapped provider tools are not exposed to agents. Live reads were verified historically; no live writes were exercised, and disconnecting an account removes its usable authorization.

The three R&D wrappers are confined to `evals/rd_a/llm_experiment.py`; they do not expand production agent allowlists. Their operation enum and inner MCP schemas constrain dispatch. See [measured granularity comparison](RD_A_RESULTS.md) and [single grounded proposal](../evals/results/single_grounded_proposal.md).
