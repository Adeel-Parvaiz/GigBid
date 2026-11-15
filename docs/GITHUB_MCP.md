# A5: Official GitHub MCP integration

GigBid consumes GitHub's official MCP server as its second third-party server, alongside official Upwork MCP. The GitHub server was not written for this project. Its Linux binary is pinned to release v2.1.0; the installer verifies the archive against GitHub's published checksum before installing it. The source URLs, archive digest and executable digest are recorded in `evals/results/github_mcp_runtime.json`.

One-line trust rationale: use GitHub's maintained server for repository evidence, run it with write operations disabled, and independently restrict the client to three read tools; repository text remains untrusted evidence rather than instructions or proof of business outcomes.

## Connection and permissions

Run `python -m scripts.install_github_mcp` inside the configured WSL environment, then start GigBid normally. Settings includes Connect GitHub. The official server performs OAuth itself; no GitHub password or PAT is collected by GigBid. In this headless WSL environment it supplies a GitHub device authorization URL and a short code through MCP URL elicitation. They appear only in the authenticated user's Settings response, not in the model's tool context or committed evidence. Enter that code on GitHub's authorization page.

Each application user gets a separate official MCP process and authenticated session. A single background task owns the session and serializes its requests, so AnyIO cancel scopes do not cross HTTP-request tasks. OAuth tokens remain in the official server's memory. After an API restart or Disconnect, reconnect GitHub; imported evidence remains persisted. Upwork's separate encrypted authorization is unaffected.

The server runs with `--read-only`, limited repository/context toolsets and only OAuth scope `read:user` (read-only profile access). It requests neither `repo` nor `public_repo`, because those grant repository write permissions. Public repository reads require no repository scope. The official server was checked with this narrower scope and still exposes the required read tools. The earlier pending `public_repo` authorization was cancelled locally before the user authorized it. Allowed tools are `get_me`, `get_file_contents` and `search_repositories`; other names are rejected before dispatch. SDK input schemas are checked before each call, and reads have bounded timeouts. See [GitHub's scope documentation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps).

## Repository evidence

The user imports a README from their own authenticated GitHub owner account and explicitly confirms authorship. Collaborator-owned repositories are not supported by this UI. Ownership alone is not proof of authorship, which is why a separate user assertion is required. Repository names and relative README paths are validated; traversal and arbitrary file imports are rejected.

The importer consumes text through GitHub MCP, including embedded text resources or structured/base64 file content. It does not scrape GitHub pages, clone a repository or execute README commands. Text is bounded, attributed to its repository/path/ref and hashed. The evidence type is `readme`; skills are not invented and outcome is null. The source README is not proof of earnings, hiring, client satisfaction or authorship beyond the user's confirmation. Only the captured README text is imported, not the entire repository. Resource-link-only and binary responses are refused.

Imported records are encrypted and scoped by application user in the existing local vault. Re-importing the same owner/repository/path/ref updates that evidence id without duplicating it. The Portfolio MCP server loads only the requesting user's imported evidence when the server receives `PORTFOLIO_USER_ID`. The application's stdio Portfolio MCP connection supplies that user identity and binds the freelancer filter. GigSim/dataset launchers now use this MCP retrieval path, so a new request can find imported evidence without restarting the API. HTTP Portfolio deployments require a separately tenant-bound server for personalized imports; this local workflow uses stdio.

## Verification

- Full Python suite: 133 passed, two unrelated infrastructure skips. `evals/results/github_mcp_tests.json` records the output.
- Chromium suite: ten passed, including the repository/authorship consent UI. `evals/results/github_mcp_playwright.json` records the result. Provider responses in this UI test are explicitly mocked.
- Actual MCP fixture tests cover read-only allowlisting, ownership/assertion and path checks, encrypted persistent imports, deduplication, API user isolation, and import retrieval through a separate Portfolio MCP process without cross-user leakage.
- The actual official v2.1.0 binary initialized successfully in read-only mode, listed 15 tools and initiated OAuth/device authorization through URL elicitation. Account authorization and a real repository read require the user's consent; fixture tests are not substitutes for those live results.

Live authorization and import evidence will be recorded separately after consent. No GitHub repository writes, issues or pull requests are made by this integration.

Official references: [GitHub MCP source and releases](https://github.com/github/github-mcp-server), [official OAuth documentation](https://github.com/github/github-mcp-server/blob/main/docs/oauth-login.md), [server configuration](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md).
