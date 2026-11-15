"""Write a concise report from actual Playwright and regression outputs."""
from __future__ import annotations

import json
import re
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    result = json.loads((root / "evals/results/playwright.json").read_text())
    validation = json.loads((root / "evals/results/playwright_validation.json").read_text())
    stats = result["stats"]
    if result["returncode"] or any(validation[key]["returncode"] for key in ("frontend_build", "e2e_types", "backend_tests")):
        raise SystemExit("Browser/build/regression validation has not passed")
    cases = []

    def visit(suites):
        for suite in suites:
            for spec in suite.get("specs", []):
                for test in spec.get("tests", []):
                    cases.append((test["projectName"], spec["title"], test["results"][-1]["status"]))
            visit(suite.get("suites", []))

    visit(result["browser_report"]["suites"])
    backend = re.search(r"\d+ passed[^\n]*", validation["backend_tests"]["stdout"])
    lines = ["# Frontend Playwright verification", "",
             f"Run: {result['finished_at_pkt']}. **{stats['expected']} passed, {stats['unexpected']} failed, "
             f"{stats['flaky']} flaky, {stats['skipped']} skipped**, using two browser workers.", "",
             "Sources: `evals/results/playwright.json`, `playwright_initial.json`, and `playwright_validation.json`.", "",
             "HTML report: [apps/web/playwright-report/index.html](../apps/web/playwright-report/index.html). "
             "Reports and test artifacts are generated/ignored locally and uploaded by the existing CI artifact step.", "",
             "## Observed browser coverage", "", "| Project | Test | Result |", "|---|---|---|"]
    for project, title, state in cases:
        lines.append(f"| {project} | {title} | {state} |")
    lines += ["", "The approval test exercises both mouse hover and keyboard focus for evidence tooltips. "
              "The onboarding test changes the hourly rate and Connects budget, saves them and verifies persistence after a reload.", "",
              "## Failures found and fixed", "",
              "The initial run passed six tests and failed two; its JSON and the original trace/screenshot artifacts are preserved "
              "under `evals/results/playwright_initial.json` and `.local-models/playwright-initial` in WSL.", "",
              "- The degraded-state assertion matched both the global banner and the actionable error card. It now selects the alert containing the retry button, while keeping the banner assertions.",
              "- Parallel browser requests exposed a backend exception while reading a run (`created_at` unexpectedly None). "
              "The shared SQLite connections now serialize complete store operations with a reentrant lock. "
              "Concurrent run/settings and user-registration/login regressions exercise identity and timestamp integrity. "
              "The exact upstream cause was not proven; serializing shared-connection operations follows "
              "[Python's SQLite threading guidance](https://docs.python.org/3.14/library/sqlite3.html#sqlite3.connect). "
              "A [related CPython concurrency issue](https://github.com/python/cpython/issues/118172) documents why shared connection access needs care.", "",
              "## Additional validation", "",
              "- Frontend production build: passed.", "- Playwright TypeScript checks: passed.",
              f"- Backend regression suite: {backend.group(0) if backend else 'see raw validation output'}.", "",
              "## Isolation and limits", "",
              "Actual Chromium drives React and FastAPI. The UI suite explicitly uses the small sample corpus and deterministic HeuristicLLM "
              "to test UI wiring; it is not a real-model quality benchmark. The degraded-mode test deliberately mocks health/job responses. "
              "Real-model API evidence remains separate in [REAL_AGENT_BEHAVIOUR.md](REAL_AGENT_BEHAVIOUR.md).", "",
              "Temporary servers use ports 13000 and 18000, never reuse demo servers, keep databases in memory and stop after the tests. "
              "The demo ports 3000 and 8000 remain closed. No live marketplace, email or calendar writes are made.", "",
              "Chromium is covered; Firefox and WebKit are not. The phone project covers unauthenticated sign-in redirection and horizontal overflow, "
              "not every authenticated screen at phone width.", "",
              "## Reproduce", "", "Configured WSL checkout:", "", "```bash",
              "cd ~/gigbid", "source .venv-linux/bin/activate", "python -m scripts.run_frontend_tests", "```", "",
              "With system Node and Chromium dependencies on a fresh Linux checkout:", "", "```bash",
              "pip install -e '.[dev]'", "cd apps/web", "npm ci", "npx playwright install --with-deps chromium", "npm run test:e2e", "```", ""]
    output = root / "docs/FRONTEND_TESTS.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
