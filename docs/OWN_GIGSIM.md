# Our GigSim service

The complete application workflow now has 20 passing checks and four browser screenshots, including abrupt restart recovery and browser approval. See [workflow verification and exact assignment requirements](GIGSIM_WORKFLOW_VERIFICATION.md).

GigBid now includes its own HTTP marketplace simulator, implemented in `apps/gigsim/main.py`. This is the project's GigSim implementation. Job text comes from the documented dataset; account histories, conversations and client outcomes remain synthetic. It makes no compatibility claim about an external instructor implementation.

The default Docker Compose stack also runs this service at `http://localhost:8003`, persists its SQLite state in the `appdata` volume, and routes the marketplace MCP through its reviewed REST contract. Compose requires a unique `GIGSIM_API_TOKEN`; the same token is passed to the simulator and MCP adapter without being printed in logs.

From the WSL checkout with the virtual environment activated:

```bash
python -m scripts.run_gigsim --with-api
```

This starts GigSim on localhost:8003, the authenticated marketplace MCP server on localhost:8001, and GigBid API on localhost:8000. It reads the existing `.env` model configuration. Start the frontend separately with `python -m scripts.run_frontend`. Ctrl+C stops the launched services. Running without `--with-api` starts only GigSim and MCP. Services bind to loopback and are not publicly deployed.

The launcher generates separate REST and MCP tokens in ignored `.local-models/gigsim/local-tokens.json`. It keeps account state in `.local-models/gigsim/state.sqlite`. Restarting preserves Connects, drafts, submissions, messages and idempotency records. The local launcher uses one reviewer account; the service supports independent accounts through its token mapping. The REST contract is `config/gigsim_contract.json`; an authenticated OpenAPI schema is served at `/openapi.json`.

Nine marketplace operations support job search and details, client history, Connects balance, draft previews/creation, submission, thread/message reads and message sending. Previews create no draft and spend no Connects. Only submission spends Connects. A repeated submission of the same draft charges once, even with a new idempotency key. Reusing an operation's key with a changed payload returns 409. SQLite transactions serialize concurrent writes across processes. Tokens select the account; users cannot specify another account in a request.

`GET /v1/outcomes` returns the authenticated account's simulated reply/interview/hire outcomes. These are deterministic for a seed and proposal key using the existing documented rule-based client model. Preferences and probabilities are not exposed through marketplace MCP. This endpoint is for evaluating simulator behavior; it is not real hiring evidence. Without a hidden-preferences file, the simulator derives skill preferences from public job requirements and uses no budget ceiling. The seed defaults to 7. The simulator does not automatically generate new conversation threads from simulated reply outcomes.

Validation includes REST authentication, schema rejection, gold-label exclusion, account isolation, persistence after restart, insufficient Connects, idempotency conflict, 16 concurrent submissions with one charge, and all nine operations over actual HTTP plus authenticated MCP. The real-model verifier uses disposable state and scripted approvals only inside this synthetic service:

```bash
python -m pytest -q
python -m evals.runners.verify_owned_gigsim
```

Real-model results are recorded in `evals/results/owned_gigsim_real_agent.json`; the initial run is retained separately. A real model can skip a gold-bid job or produce a draft blocked by grounding. These outcomes are recorded, not forced into successful submissions. Empty grounded drafts stop with `needs_attention` before any preview call.

The verified run submitted the AI/ML proposal after a scripted sandbox approval and spent 12 Connects. The other two persona cases stopped for attention after grounding removed their text. The full regression suite passed 115 tests with two infrastructure skips. `evals/results/owned_gigsim_tests.json` records test output; `owned_gigsim_launcher.json` records successful GigSim/API health checks and confirms launched ports were closed afterward.

This is a local assignment simulator. It does not implement live payments, production account registration, a production rate limiter, or an independent model of real client behavior. GigBid's usual approval gate remains in effect; the simulator API itself treats its bearer token as authorization to submit synthetic proposals.
