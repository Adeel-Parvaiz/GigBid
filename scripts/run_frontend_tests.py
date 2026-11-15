"""Run isolated Playwright UI tests with the project-local WSL Node/browser runtime."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def main():
    cache = ROOT / ".local-models"
    cached = sorted((cache / "node-runtime").glob("node-*/bin/node"))
    node = str(cached[-1]) if cached else shutil.which("node")
    if not node:
        raise SystemExit("Node.js is missing; use the configured WSL project or install Node.js first.")
    web = ROOT / "apps/web"
    env = {**os.environ, "PATH": os.pathsep.join([str(Path(node).parent), str(Path(sys.executable).parent), os.environ.get("PATH", "")])}
    libraries = cache / "playwright-libs/root/usr/lib/x86_64-linux-gnu"
    if libraries.exists():
        env["LD_LIBRARY_PATH"] = str(libraries) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    if (cache / "playwright-browsers").exists():
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(cache / "playwright-browsers"))
    cli = web / "node_modules/@playwright/test/cli.js"
    if not cli.exists():
        npm = shutil.which("npm", path=env["PATH"])
        if not npm:
            raise SystemExit("npm is missing from the selected Node installation.")
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=web, env=env, check=True)
    started = datetime.now(ZoneInfo("Asia/Karachi")).isoformat()
    command = [node, str(cli), "test", "--workers=2", *sys.argv[1:]]
    process = subprocess.Popen(command, cwd=web, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines = []
    for line in process.stdout:
        print(line, end="", flush=True)
        lines.append(line)
    code = process.wait()
    result = {"started_at_pkt": started, "finished_at_pkt": datetime.now(ZoneInfo("Asia/Karachi")).isoformat(),
              "returncode": code, "scope": "Real Chromium browser against isolated FastAPI/React servers; deterministic HeuristicLLM and sample data; degraded-mode responses deliberately mocked in that test.",
              "node_version": subprocess.check_output([node, "--version"], text=True).strip(),
              "stdout": "".join(lines), "html_report": "apps/web/playwright-report/index.html"}
    a6 = any('playwright.a6.config' in arg for arg in sys.argv[1:])
    if a6:
        result['scope'] = 'Actual marketplace MCP process killed/restarted behind HTTP API and Chromium; synthetic GigSim and HeuristicLLM. No mocked outage HTTP responses or live account writes.'
        result['html_report'] = 'apps/web/playwright-report-a6/index.html'
    report = web / "test-results/results.json"
    if report.exists():
        data = json.loads(report.read_text())
        result["stats"] = data.get("stats")
        result["browser_report"] = data
    destination = ROOT / ('evals/results/client_discipline_browser.json' if a6 else 'evals/results/playwright.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved {destination}", flush=True)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
