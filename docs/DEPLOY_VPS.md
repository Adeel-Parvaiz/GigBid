# VPS deployment (prepared, not provisioned)

The VPS profile publishes only Caddy on ports 80 and 443. Caddy obtains and renews
TLS certificates, routes `/api/*` to FastAPI, routes the Upwork OAuth result pages
to FastAPI, and serves the React app for all other paths. PostgreSQL is expected
to be managed externally; Redis, GigSim state and API run state use persistent
Docker volumes.

## Required before launch

- A Linux VPS with Docker Engine and Docker Compose v2.24 or newer. Free-tier
  VPS capacity, resources and uptime are not guaranteed; some providers require
  payment-card verification even for free plans.
- A DNS name with an `A` record pointing to the VPS public IPv4 address. Allow
  inbound TCP ports 80 and 443 (and UDP 443 for HTTP/3); restrict SSH to your IP.
- A managed PostgreSQL database and a **newly rotated** connection credential.
  The earlier local credential was exposed and must not be reused.
- A persistent Fernet key for OAuth-token encryption and fresh application,
  marketplace, GigSim, and reviewer secrets. Do not commit `.env` or paste secrets
  into chat.
- An LLM configuration. `LLM_BACKEND=heuristic` is suitable only for a smoke
  test; real proposal generation needs a configured model endpoint and key.

## Configure and launch

On the VPS, clone the public repository and create an untracked environment file:

```sh
git clone https://github.com/Adeel-Parvaiz/GigBid.git
cd GigBid
cp .env.example .env
```

Edit `.env` on the VPS and set:

- `DOMAIN` to the DNS name.
- `DATABASE_URL` to the rotated managed PostgreSQL URL, including its required
  TLS options.
- `PUBLIC_UPWORK_CALLBACK_URL` to
  `https://<DOMAIN>/api/connections/upwork/callback`. Register that exact URL
  with the OAuth provider before enabling Upwork.
- Fresh random values for `APP_SECRET_KEY`, `POSTGRES_PASSWORD`,
  `MARKETPLACE_MCP_TOKEN`, `GIGSIM_API_TOKEN`, `REVIEWER_PASSWORD`, and a valid
  `OAUTH_ENCRYPTION_KEY`.
- `GIGBID_DATA_DIR=data/sample` for a small smoke deployment. To use the prepared
  Kaggle corpus instead, obtain the source data under its license, run the
  documented dataset preparation, then set the corpus path before building.
- `LLM_BACKEND` and the model endpoint/key. Avoid downloading local models on a
  constrained free VPS.

Build and start the production profile:

```sh
docker compose -f infra/docker-compose.yml -f infra/docker-compose.vps.yml --env-file .env up -d --build
docker compose -f infra/docker-compose.yml -f infra/docker-compose.vps.yml --env-file .env ps
```

Only Caddy should have public host port bindings. Verify `https://<DOMAIN>/`,
`https://<DOMAIN>/api/health`, login, a sample job run, approval, and a client
reply. Test persistence by leaving an approval pending, restarting the API and
worker, then approving once from the UI.

## Keep available and secure

- Configure provider-side backups for managed PostgreSQL. Back up Docker volumes
  containing Redis, runs, OAuth tokens, and GigSim state before upgrades.
- Keep `.env` only on the host with restrictive file permissions. Rotate secrets
  if the host or backups are exposed.
- Monitor `docker compose ... ps` and container logs; renewals are automatic while
  DNS and ports remain correct.
- The current Vercel deployment has Vercel authentication protection. If using
  that frontend, disable deployment protection in Vercel only when intentionally
  making it public. Set its build-time `VITE_API_URL` to
  `https://<DOMAIN>/api` and set backend `CORS_ORIGINS` to the exact Vercel
  origin, then redeploy the frontend. Alternatively, this profile serves the
  frontend and API together on the VPS, avoiding cross-origin configuration.

This document and Compose override prepare deployment but do not provision a VPS,
create a database, set DNS, or establish public availability. Those require the
user-created provider account and its credentials.
