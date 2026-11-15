# Runbook
For a public VPS deployment, use [the VPS deployment guide](DEPLOY_VPS.md) and
the production-only `infra/docker-compose.vps.yml` override. The standard Compose
file remains the local development setup.

## Start
`cp .env.example .env`, set unique secrets (including `GIGSIM_API_TOKEN`), then run `docker compose -f infra/docker-compose.yml --env-file .env up --build`. The default stack runs the project-owned GigSim on `127.0.0.1:13003` and routes the marketplace MCP through it. Pull models when needed: `docker compose exec ollama ollama pull qwen3:4b` (and the writer model in `agent/config.yaml`).
Reviewer login is seeded from `REVIEWER_EMAIL` / `REVIEWER_PASSWORD`.

Interactive job and conversation runs, approval resumes, retries and graph replays are queued through ARQ. The worker and API must use the same persistent `RUNS_DB` path; SSE events are stored there so the API can stream progress produced by the worker. Redis uses AOF with a persistent Compose volume for queued work.
## Scouting interval (justify before live mode)
Sample/GigSim: every 5 min (`worker.scout_interval_minutes`). **Live Upwork: use >= 120 min**, read-only, a handful of saved searches, no parallel polling.
Reason: Upwork treats scraping-like polling and unapproved automation as violations. Only the official MCP server / approved APIs; nothing is sent without human approval and confirmation on Upwork.
## Failure drills (the viva)
- **Marketplace MCP down**: UI banner via `/health`; `/jobs` returns 503; new runs end as `queued_degraded`; `POST /admin/retry-degraded` (or the worker) requeues when it returns. Code: `agent/marketplace_mcp.py` (maps to `marketplace_unavailable`), `apps/api/runs.py::_settle`.
- **API killed with a pending approval**: restart; `GET /approvals/pending` reads the interrupt from the Postgres checkpoint; approve; submitted once (`tests/integration/test_api.py::test_pending_approval_survives_api_restart_and_submits_once`).
- **Worker killed mid-run**: its `running` rows become `needs_attention` on next start; `POST /runs/{id}/retry` continues from the checkpoint.
- **Exactly-once**: idempotency key = hash(freelancer, job, final text), enforced by the marketplace server.
## Switching to live mode
Only the adapter changes (`MARKETPLACE_MODE`); the graph talks to the same port. Live Upwork adapter is not built.
