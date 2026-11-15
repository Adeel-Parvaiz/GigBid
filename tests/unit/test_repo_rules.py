import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("rules", ROOT / "scripts/check_repo_rules.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def test_repo_currently_passes_every_rule():
    assert rules.no_secrets() == [] and rules.prompts_only_in_prompts_dir() == [] and rules.gigsim_unchanged() == []


def test_fallback_scanner_excludes_virtualenv_dependencies(tmp_path, monkeypatch):
    monkeypatch.setattr(rules, "ROOT", tmp_path)

    def no_git(*args, **kwargs):
        raise FileNotFoundError("git unavailable")

    monkeypatch.setattr(rules.subprocess, "check_output", no_git)
    dependency = tmp_path / ".venv-linux/lib/site-packages/vendor"
    dependency.mkdir(parents=True)
    (tmp_path / ".venv-linux/pyvenv.cfg").write_text("home = python")
    (dependency / "example.py").write_text('KEY = "sk-' + "a" * 30 + '"')
    source = tmp_path / "app.py"
    source.write_text("value = 1")
    (tmp_path / ".env").write_text("LLM_BACKEND=openai_compat")
    assert rules.files() == [source]
    assert rules.no_secrets() == []
    source.write_text('KEY = "sk-' + "b" * 30 + '"')
    assert rules.no_secrets()


def test_tracked_env_file_is_still_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(rules, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("LLM_BACKEND=openai_compat")
    monkeypatch.setattr(rules.subprocess, "check_output", lambda *args, **kwargs: b".env\n")
    assert rules.no_secrets() == ["tracked env file: .env"]


def test_secret_scanner_and_prompt_scanner_and_readme_trace_actually_bite(tmp_path, monkeypatch):
    f = tmp_path / "x.py"
    f.write_text('KEY = "sk-' + "a" * 30 + '"\nP = "You are a careful assistant. Return only JSON matching the schema please."\n')
    monkeypatch.setattr(rules, "ROOT", tmp_path)
    monkeypatch.setattr(rules, "files", lambda suffixes=None: [f])
    assert rules.no_secrets() and rules.prompts_only_in_prompts_dir()
    (tmp_path / "evals/results").mkdir(parents=True)
    (tmp_path / "evals/results/r.json").write_text(json.dumps({"a": {"b": 0.5}}))
    (tmp_path / "README.md").write_text("<!-- result: r.json:a.b = 0.5 --> ok <!-- result: r.json:a.b = 0.9 --> bad")
    assert len(rules.readme_numbers_trace()) == 1


def test_readme_tags_with_hyphenated_filenames_are_checked_not_silently_ignored(tmp_path, monkeypatch):
    (tmp_path / "evals/results").mkdir(parents=True)
    (tmp_path / "evals/results/decision_eval_ai-ml-engineer.json").write_text(json.dumps({"a": {"recall@5": 0.5}}))
    (tmp_path / "README.md").write_text("<!-- result: decision_eval_ai-ml-engineer.json:a.recall@5 = 0.9 -->")
    monkeypatch.setattr(rules, "ROOT", tmp_path)
    assert len(rules.readme_numbers_trace()) == 1
