"""Rules CI must enforce (assignment): no secrets in repo; nothing under gigsim/ changed; every prompt in
agent/prompts/; every number in README.md traces to evals/results/.   python scripts/check_repo_rules.py"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(r"(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[bp]-[0-9A-Za-z-]{10,}|ghp_[A-Za-z0-9]{30,})")
PROMPT_HINT = re.compile(r"(?i)(you are an? |untrusted data|return only json)")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", ".pytest_cache", ".ruff_cache", ".local-models"}


def files(suffixes=None):
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, stderr=subprocess.DEVNULL).decode().split()
        paths = [ROOT / p for p in out]
    except Exception:  # noqa: BLE001
        paths = []
        for directory, dirs, names in os.walk(ROOT):
            base = Path(directory)
            dirs[:] = [name for name in dirs
                       if name not in SKIP_DIRS and not (base / name / "pyvenv.cfg").is_file()]
            # An archive checkout has no tracked-file information; local ignored config is not source.
            # With Git available, a tracked .env is still included above and rejected by no_secrets().
            paths.extend(base / name for name in names if name != ".env")
    return [p for p in paths if p.is_file() and (suffixes is None or p.suffix in suffixes)]


def no_secrets() -> list[str]:
    bad = [f"tracked env file: {p.relative_to(ROOT)}" for p in files() if p.name == ".env"]
    for p in files():
        if p.suffix in {".png", ".jpg", ".pdf", ".zip", ".sqlite", ".lock"} or p.stat().st_size > 2_000_000:
            continue
        for m in SECRET.finditer(p.read_text(errors="ignore")):
            bad.append(f"secret-like string in {p.relative_to(ROOT)}: {m.group(0)[:8]}...")
    return bad


def gigsim_unchanged() -> list[str]:
    g, manifest = ROOT / "gigsim", ROOT / "gigsim.MANIFEST.json"
    if not g.exists():
        return []                                   # not provided yet: nothing to protect
    if not manifest.exists():
        return ["gigsim/ exists but gigsim.MANIFEST.json is missing: run `python scripts/check_repo_rules.py --record-gigsim` on the pristine copy"]
    want = json.loads(manifest.read_text())
    have = {str(p.relative_to(g)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(g.rglob("*")) if p.is_file()}
    return [f"gigsim/{k} changed" for k in set(want) | set(have) if want.get(k) != have.get(k)]


def prompts_only_in_prompts_dir() -> list[str]:
    bad = []
    for p in files({".py"}):
        rel = p.relative_to(ROOT)
        if rel.parts[0] in {"tests", "evals", "scripts"} or "prompts" in rel.parts:
            continue
        tree = ast.parse(p.read_text())
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if id(node) in docstrings:
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) > 60 and PROMPT_HINT.search(node.value):
                bad.append(f"inline prompt-like string in {rel}:{node.lineno}")
    return bad


def readme_numbers_trace() -> list[str]:
    """README numbers must be tagged:  <!-- result: decision_eval.json:base.bid_or_skip.f1 = 1.0 -->  and match the file."""
    readme, bad = (ROOT / "README.md").read_text(), []
    for f, path, val in re.findall(r"<!-- result: ([\w.-]+):([\w.@-]+) = ([^ ]+) -->", readme):
        try:
            node = json.loads((ROOT / "evals/results" / f).read_text())
            for k in path.split("."):
                node = node[k]
        except Exception:  # noqa: BLE001
            bad.append(f"README cites {f}:{path} which does not exist")
            continue
        if str(round(node, 4) if isinstance(node, float) else node) != val:
            bad.append(f"README says {f}:{path} = {val} but the results file has {node}")
    return bad


def main() -> int:
    if "--record-gigsim" in sys.argv:
        g = ROOT / "gigsim"
        (ROOT / "gigsim.MANIFEST.json").write_text(json.dumps(
            {str(p.relative_to(g)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(g.rglob("*")) if p.is_file()}, indent=1))
        return 0
    problems = {"secrets": no_secrets(), "gigsim": gigsim_unchanged(), "prompts": prompts_only_in_prompts_dir(),
                "readme-numbers": readme_numbers_trace()}
    for name, errs in problems.items():
        print(f"{'FAIL' if errs else 'ok  '} {name}")
        for e in errs:
            print("   ", e)
    return 1 if any(problems.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
