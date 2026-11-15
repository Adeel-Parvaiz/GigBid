# B1 — Portfolio ingestion and incremental indexing

B1 is implemented for all six source types. In Settings, use **Add portfolio evidence**. Files are private to the signed-in user and their assigned persona. Agents retrieve their contents through the read-only Portfolio MCP server.

| Source | Loader | Input |
|---|---|---|
| CV | `rag/ingest/loaders.py` | Text PDF, Markdown or UTF-8 text |
| Case study | same | Markdown or UTF-8 text |
| Repository README | `GitHubMCP.import_file` then document loader | README read using the official GitHub MCP server's `get_file_contents` |
| Repository code | same | Explicit relative source-file path, read using GitHub MCP; never executed |
| Review | document loader | UTF-8 text/Markdown, or JSON objects with a `text` field |
| Past proposal | document loader | Same text/JSON formats, with an explicitly supplied outcome |

Repository imports require the existing read-only GitHub connection, an owned repository and authorship confirmation. No GitHub writes, scraping or direct GitHub REST calls are used. Source code cannot be uploaded through the local-file endpoint. The earlier GitHub README button also sends new imports through the chunking pipeline. Actual account authorization remains a separate user action; transport tests use an explicit local MCP fixture, not an authenticated real GitHub account.

## Metadata and truthfulness

Every new chunk carries `persona`, `type`, `project`, `skills`, `date`, `client_industry`, `outcome`, `source`, document/evidence IDs, content hash and chunk position. Persona is assigned from the authenticated account, not supplied by the form. Project, title and authorship confirmation are required. Unknown date/industry are retained as explicit null values; they are not fabricated. Proposals require an outcome, with `unknown` accepted when unavailable. Review/proposal JSON files should describe one project and share the supplied document metadata; import separate files for different outcomes or projects.

The user supplies skills and outcomes; ingestion does not infer or independently verify them. Synthetic material remains explicitly tagged `synthetic`, including synthetic content read through the GitHub transport. Source transport and content provenance are recorded separately. Legacy corpus items receive persona/project/industry metadata on load without rewriting the versioned dataset.

## Incremental behavior

`rag/ingest/store.py` uses overlapping fixed chunks (1,200 characters, overlap 150). A document's stable identity includes account, persona, source and type; unchanged uploads return immediately with zero embedded chunks. Changes replace that document atomically, preserve unchanged chunk IDs/vectors, embed changed/new chunks and remove obsolete chunks. Metadata changes also update the saved revision. Re-upload the same filename/type to update an uploaded document; changing a Git ref creates a distinct source version.

Documents, chunk text and vectors are persisted together in a user-scoped encrypted record in the existing vault. Stored vectors currently use the application's deterministic hashing embedder, not a claim of neural indexing; neural retrieval comparisons are documented separately. DenseIndex supports incremental upsert/removal and retains unchanged vectors. Portfolio MCP reloads changed document revisions before every search/fetch/skill request, including in an already-open MCP session. Persisted hashing vectors are reused on new sessions; the small base corpus is still initialized per server process. BM25 postings refresh when the corpus changes.

The UI exposes document revisions and chunk counts, removal, and MCP-backed search. A file becomes searchable immediately without restarting the API or MCP session. Past proposals remain excluded from ordinary portfolio retrieval unless explicitly requested; the UI search passes the selected evidence type.

## API and limits

All routes require GigBid bearer authentication and operate only on the authenticated user's records:

- `GET/POST /portfolio/documents`: list metadata or ingest a base64-encoded file plus metadata.
- `POST /portfolio/github`: read a specified README/code file over GitHub MCP and ingest it.
- `DELETE /portfolio/documents/{id}`: remove owned evidence and its indexed chunks.
- `GET /portfolio/search?query=...&kind=...`: search through an official SDK in-memory Portfolio MCP client.

The upload API supports files up to 2 MB, extracted text up to one million characters, and PDFs up to 100 pages. Encrypted, corrupt and scanned/image-only PDFs are rejected with a readable error; OCR is not included. GitHub's existing text/content-window limits still apply. Code is treated as untrusted text. Original upload binaries are not retained; extracted text and attribution are encrypted. These ingestion APIs are user actions; agent nodes continue to use MCP tools only.

## Verification

- Full Python suite: **157 passed, 2 infrastructure skips**. New tests cover actual PDF text extraction, all loaders, chunk metadata, unchanged uploads, incremental vector reuse, updates/deletion, persistence and cross-user isolation.
- An official SDK client kept the same Portfolio MCP session open while evidence was added, updated and deleted, proving refresh without restart.
- GitHub tests invoke `get_file_contents` through an actual stdio MCP fixture for README and Python source, including owner/authorship checks and the existing write denial policy.
- **12 Chromium checks passed**, including real API upload/update/search/remove flows on desktop and phone; ingestion responses are not mocked.
- Frontend typecheck/build passed. The Portfolio schema snapshot was intentionally updated for the additional metadata fields and code filter.

Evidence: [validation record](../evals/results/b1_validation.json), [browser screenshot](../evals/results/b1/portfolio-upload-search.png), and `tests/unit/test_portfolio_ingestion.py` / `tests/integration/test_portfolio_ingestion.py` / `apps/web/tests/e2e/portfolio-ingestion.spec.ts`.

Reproduce with `pip install -e ".[dev]"`, `python -m pytest -q`, and `python -m scripts.run_frontend_tests`. Generate frontend API types/build with `npm run gen:api && npm run build` in `apps/web`.
