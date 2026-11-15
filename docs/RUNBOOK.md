# Runbook
For a public VPS deployment, use [the VPS deployment guide](DEPLOY_VPS.md) and
the production-only `infra/docker-compose.vps.yml` override. The standard Compose
file remains the local development setup.

## Start
`cp .env.example .env`, set unique secrets (including `GIGSIM_API_TOKEN` and
`PORTFOLIO_MCP_TOKEN`), and generate a persistent Fernet `OAUTH_ENCRYPTION_KEY`
before running `docker compose -f infra/docker-compose.yml --env-file .env up --build`.
The API/worker and Portfolio MCP receive the same internal token and OAuth key
from `.env`. The default stack runs the project-owned GigSim on
`127.0.0.1:13003` and routes the marketplace MCP through it. Pull models when
needed: `qwen3:4b-instruct` for all open-profile agent nodes and `qwen2.5:3b` for the
configured analyst, risk, and liaison-intent fallbacks. For example:
`docker compose -f infra/docker-compose.yml --env-file .env exec ollama ollama pull qwen3:4b-instruct`
and repeat with `qwen2.5:3b`. The smaller local writer/critic model uses less
memory than `gpt-oss:20b`; its output quality is not equivalent. The local
profile caps each completion at 768 tokens. Use the instruct tag rather than
the thinking-only `qwen3:4b` tag for bounded CPU inference.
Reviewer login is seeded from `REVIEWER_EMAIL` / `REVIEWER_PASSWORD`.

Interactive job and conversation runs, approval resumes, retries and graph replays are queued through ARQ. The worker and API must use the same persistent `RUNS_DB` path; SSE events are stored there so the API can stream progress produced by the worker. Redis uses AOF with a persistent Compose volume for queued work.

## Back up and restore local appdata

The shared `appdata` volume contains `runs.sqlite`, `users.sqlite`,
`oauth/tokens.sqlite`, `portfolio_index.sqlite`, `gigsim/state.sqlite`, and
`workspace.sqlite`, plus non-SQLite audit files such as
`marketplace_audit.jsonl`. The backup utility uses SQLite's online backup API,
checks SQLite integrity, snapshots ordinary files, and records SHA-256 checksums
in the archive manifest. It excludes transient SQLite `-wal`/`-shm` sidecars.

Backups contain application and audit data; store them somewhere access-controlled
and encrypted at rest. The OAuth database is encrypted, but the backup is not.
Keep the exact `OAUTH_ENCRYPTION_KEY` separately and securely: without it, OAuth
tokens and encrypted portfolio vectors cannot be read after restore. The archive
checksums detect corruption; they do not authenticate who created an archive.

Run on the Docker host from the project root. Stop every writer first so the
several databases and audit log represent a consistent point in time:

```sh
mkdir -p backups
docker compose -f infra/docker-compose.yml --env-file .env stop api worker portfolio-mcp marketplace-mcp workspace-mcp gigsim
docker compose -f infra/docker-compose.yml --env-file .env run --rm --no-deps \
  -v "$PWD/backups:/backups" api \
  python -m scripts.backup_appdata backup --source /data --backup-dir /backups
docker compose -f infra/docker-compose.yml --env-file .env start gigsim workspace-mcp marketplace-mcp portfolio-mcp api worker
```

Save the archive path printed by the backup command outside the VPS as well. To
restore, stop the same services, put the archive in `backups/`, then run:

```sh
docker compose -f infra/docker-compose.yml --env-file .env stop api worker portfolio-mcp marketplace-mcp workspace-mcp gigsim
docker compose -f infra/docker-compose.yml --env-file .env run --rm --no-deps \
  -v "$PWD/backups:/backups" api \
  python -m scripts.backup_appdata restore \
  --archive /backups/<archive-name>.tar.gz --destination /data --replace-existing
docker compose -f infra/docker-compose.yml --env-file .env start gigsim workspace-mcp marketplace-mcp portfolio-mcp api worker
```

`--replace-existing` replaces the contents of the entire shared `appdata`
volume, not one selected database. Restore validates archive paths, checksums,
and each SQLite database before replacement; it rolls back the replacement if
installation fails. Keep a separate copy of the pre-restore volume until the
restored application has been verified. This procedure does not back up Redis
(`redisdata`), local PostgreSQL (`pgdata`), Ollama models, Caddy state, or an
external managed PostgreSQL database; handle those using their own backup
procedures.

## Other persistent volumes

The appdata utility above is the only implemented and locally tested volume
backup/restore tool. These services have persistent storage, but their data is
not included in that archive:

| Service | Stored data | Current coverage | Backup/restore guidance |
|---|---|---|---|
| Redis | `redisdata`; AOF enabled with `appendfsync everysec` | Persistence across container restarts, not a separate backup | Stop API and worker to quiesce queue writes, then stop Redis before taking a volume snapshot. Restore only with Redis stopped, into a clean replacement volume; preserve the old volume first. Validate queue state before restarting workers. |
| Local PostgreSQL | `pgdata` | Persistent Docker volume; no project backup command | Prefer a transaction-consistent custom-format `pg_dump` and test `pg_restore` into a fresh database. Stop API/worker during restore. A raw volume snapshot must be coordinated with PostgreSQL and should not be copied while it is running. |
| Managed PostgreSQL (VPS) | Provider-managed storage | Not backed up by this repository | Enable provider-side scheduled backups/PITR and separately retain periodic TLS-protected `pg_dump` exports. Perform a restore drill into a separate database. |
| Ollama | `ollama` at `/root/.ollama` | Persistent model cache, no backup | Models can be downloaded again; back up this volume only if avoiding a large re-download is worth the storage. |
| Caddy (VPS profile only) | `caddy_data` certificates/private keys and `caddy_config` state | Persistent volumes, no backup | Stop Caddy before taking a consistent volume snapshot. Encrypt and tightly restrict these backups; restore both volumes together and verify certificate renewal. The Caddyfile itself is tracked under `infra/docker/`. |

For off-site retention, use a client-side encrypted backup tool such as Restic
to send completed archives and database dumps to a separately administered
repository (for example, another host or object-storage provider). Keep the
repository password/key separate from both the backup destination and
`OAUTH_ENCRYPTION_KEY`; configure retention, monitor backup age, and regularly
restore into isolated temporary volumes/databases. Restic encryption is a
recommendation only; no off-site destination is configured by this project.

Keep the exact `OAUTH_ENCRYPTION_KEY` stable across API, worker, and Portfolio
MCP restarts and restores. Changing it does not re-encrypt stored records:
existing OAuth records and portfolio vectors will fail decryption, typically
with Fernet `InvalidToken`. Restore the original key to recover access. If that
key is lost, affected OAuth accounts must be reconnected and encrypted imported
portfolio data must be reimported from its source. This project has no
in-place key-rotation command.

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
