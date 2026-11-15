from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"


def load_dev(path: str | None = None) -> list[dict]:
    return json.loads(Path(path or ROOT / "evals/datasets/sample_dev.json").read_text())["jobs"]


def commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "no-git"


def write_result(name: str, body: dict, corpus: str = "toy-sample-5-jobs", llm: str = "heuristic-double") -> Path:
    """Every number in the README/report must trace to one of these files."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    meta = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "commit": commit(), "corpus": corpus, "llm": llm,
            "valid_for_report": False, "why_not": "toy corpus + test-double LLM; rerun on the instructor dev set with a real model"}
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps({"meta": meta, **body}, indent=1, default=str))
    return path
