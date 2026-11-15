# AI usage
Additional tool: OpenAI Codex. Used for dataset verification/launch scripts, dataset documentation, WSL environment diagnosis, virtual-environment scanner exclusions, local open-model setup, real-model comparison instrumentation and model-comparison reporting.
Also used for actual real-model HTTP verification and the resulting fixes: failed-run persistence, duplicate analysis requests, edited-claim gating, calendar-owned scheduling fields, current-date resolution, deterministic Critic checks and persistent local API state. Initial failures and final observed behavior are preserved separately; see `docs/REAL_AGENT_BEHAVIOUR.md`.
For frontend verification, Codex installed local Node/Chromium runtime dependencies, ran Playwright, corrected an ambiguous degraded-state locator, and serialized shared SQLite connection operations after concurrent browser requests exposed a backend failure. The tests now explicitly exercise saved rate/budget persistence plus mouse and keyboard evidence tooltips. Initial failures, final browser results and regression checks are preserved in `evals/results/playwright*.json`.

Concrete correction exposed by the user's test run: Codex suggested a `.venv-linux` environment, but the repository scanner only excluded `.venv`. The user's WSL test run falsely flagged a dependency's SSH serialization example as a repository secret. The scanner now recognizes virtual environments by `pyvenv.cfg`; a regression test checks that dependencies are excluded while actual project secrets are still detected.

Real-model status must be supported by saved inference results. Configuration placeholders and a mocked HTTP unit test were not real model runs. The user clarified that none had occurred before the local-model setup and comparison recorded in `docs/OPEN_MODEL_COMPARISON.md`.

Tool: Claude (chat). Used for: scaffold, graphs, nodes, MCP servers, API, worker, UI, tests, evals, docs in this repo.
The original scaffold listed these additional test-discovered bugs. Discuss only those you actually reviewed and can explain in the viva:
- verifier treated digits in "boilerplate" as experience claims and deleted the calendar-slot sentence (fixed: `logistics` claims written by code);
- compliance's phone regex scrubbed ISO dates (fixed: date lookahead + test);
- langchain-mcp-adapters turns tool errors into normal text results by default (fixed: `handle_tool_errors=False`);
- a test that never failed because `-x` hid it / mutation checks showed a missing test for retry scoping (added).
