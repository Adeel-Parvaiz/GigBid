# Frontend Playwright verification

Run date: 2026-11-15. **14 passed, 0 failed, 0 flaky, 0 skipped** across 12 unique tests (12 desktop project runs and 2 phone project runs).

Run: `cd apps/web && npm run test:e2e`. Full JSON report: [`evals/results/part_d_playwright.json`](../evals/results/part_d_playwright.json). The approval workflow recording is [`evals/results/part_d_workflow.webm`](../evals/results/part_d_workflow.webm).

The browser suite uses the real React/FastAPI app with an isolated in-memory test setup. It ran with six workers.

## Observed browser coverage

| Project | Test | Result |
|---|---|---|
| desktop | inbox -> streamed run -> evidence on hover -> approve -> pipeline | passed |
| desktop | a pending approval survives a page refresh | passed |
| desktop | marketplace down: banner, clear error state, and it recovers | passed |
| desktop | editing a draft saves it; a policy-violating edit blocks approval | passed |
| desktop | onboarding: register, set rates, land on a ranked inbox | passed |
| desktop | unauthenticated visitors are sent to sign-in @mobile | passed |
| phone | unauthenticated visitors are sent to sign-in @mobile | passed |
| desktop | reject requires a reason and records it in analytics | passed |
| desktop | GitHub README import requires repository and authorship confirmation | passed |
| desktop | Upwork confirmation requires separate review and an attachment choice | passed |
| desktop | regenerate one evidence-backed paragraph without changing the others | passed |
| desktop | record inbox to approved proposal to client reply | passed; recording saved |
| desktop | portfolio upload is indexed, updated and searchable without restarting | passed |
| phone | portfolio upload is indexed, updated and searchable without restarting | passed |

The approval test exercises both mouse hover and keyboard focus for evidence tooltips. The onboarding test changes the hourly rate and Connects budget, saves them and verifies persistence after a reload. The analytics test confirms estimated heuristic tokens are not displayed as measured throughput or zero-dollar model cost. Browser inspection at 390px found no page-level horizontal overflow; the wide per-run analytics table scrolls within its own viewport.

## Failures found and fixed

The initial run passed six tests and failed two; its JSON and the original trace/screenshot artifacts are preserved under `evals/results/playwright_initial.json` and `.local-models/playwright-initial` in WSL.

- The degraded-state assertion matched both the global banner and the actionable error card. It now selects the alert containing the retry button, while keeping the banner assertions.
- Parallel browser requests exposed a backend exception while reading a run (`created_at` unexpectedly None). The shared SQLite connections now serialize complete store operations with a reentrant lock. Concurrent run/settings and user-registration/login regressions exercise identity and timestamp integrity. The exact upstream cause was not proven; serializing shared-connection operations follows [Python's SQLite threading guidance](https://docs.python.org/3.14/library/sqlite3.html#sqlite3.connect). A [related CPython concurrency issue](https://github.com/python/cpython/issues/118172) documents why shared connection access needs care.
- New tests initially used a stale regeneration label and expected a non-existent `Finished:` timeline item; they now select an evidence-backed paragraph and assert the actual `sent` status. Browser inspection also caught obsolete signup copy and an estimated heuristic token rate that looked measured; both were corrected.
- The raw Vite production command mishandled the workspace's `#` path and emitted an empty bundle. The build script now uses the same temporary drive alias as the dev server; the verified bundle transforms 37 modules.

## Additional validation

- Frontend production build: passed (37 modules transformed).
- OpenAPI client generation and Playwright TypeScript checks: passed.
- Focused analytics, fit-matching and API regression suite: 23 passed.
- Complete Playwright suite: 14 passed across desktop and phone projects.

## Isolation and limits

Actual Chromium drives React and FastAPI. The UI suite explicitly uses the small sample corpus and deterministic HeuristicLLM to test UI wiring; it is not a real-model quality benchmark. The degraded-mode test deliberately mocks health/job responses. Real-model API evidence remains separate in [REAL_AGENT_BEHAVIOUR.md](REAL_AGENT_BEHAVIOUR.md).

Temporary test servers use ports 13000 and 18000, never reuse demo servers, keep databases in memory and stop after the tests. The demo ports 3000 and 8000 remain closed. No live marketplace, email or calendar writes are made.

Chromium is covered; Firefox and WebKit are not. The phone project covers unauthenticated sign-in redirection and horizontal overflow, not every authenticated screen at phone width.

## Reproduce

Configured WSL checkout:

```bash
cd ~/gigbid
source .venv-linux/bin/activate
python -m scripts.run_frontend_tests
```

With system Node and Chromium dependencies on a fresh Linux checkout:

```bash
pip install -e '.[dev]'
cd apps/web
npm ci
npx playwright install --with-deps chromium
npm run test:e2e
```
