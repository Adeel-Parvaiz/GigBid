"""Report observed real-model HTTP behavior without relabelling heuristic unit tests as real runs."""
from __future__ import annotations

import json
import re
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    results = root / "evals/results"
    data = json.loads((results / "real_agent_behaviour.json").read_text())
    initial = json.loads((results / "real_agent_behaviour_initial.json").read_text())
    tests = json.loads((results / "real_agent_behaviour_tests.json").read_text())
    if data["status"] != "completed" or data["failed"] or tests["returncode"]:
        raise SystemExit("Behavior verification or regression tests have not passed")
    calls = [c for phase in data["model_phases"].values() for c in phase["calls"]]
    nodes = sorted({c["node"] for c in calls})
    models = sorted({c["model"] for c in calls})
    test_summary = re.search(r"\d+ passed[^\n]*", tests["stdout"])
    lines = ["# Actual real-model agent behavior", "",
             f"Completed {data['finished_at_pkt']}. **{data['passed']}/{len(data['checks'])} behavior checks passed**. "
             f"Regression suite: {test_summary.group(0) if test_summary else 'see raw test output'}.", "",
             "Sources: `evals/results/real_agent_behaviour.json`, `real_agent_behaviour_initial.json`, "
             "and `real_agent_behaviour_tests.json`. The first run found "
             f"{initial['failed']} failures across {len(initial['checks'])} checks. The final run adds explicit reply-send and Critic-revision checks.", "",
             "## Execution and boundaries", "",
             "These are real HTTP requests to a separate FastAPI process using `MeasuredLLM`, a measurement subclass of "
             "`OpenAICompatLLM`, against the local llama.cpp GPU server. No HeuristicLLM responses or mock model HTTP responses were used.", "",
             f"Observed models: `{', '.join(models)}` (Qwen2.5 1.5B Q4_K_M). Observed LLM roles: {', '.join(nodes)}. "
             f"Recorded {len(calls)} model HTTP responses, including schema-repair attempts. Connection-fault calls have no successful HTTP response and are recorded in the failure case.", "",
             data["scope"], "",
             "Approval requests in this verifier deliberately operate only on the isolated SampleAdapter and local WorkspaceService. "
             "They are test approvals, not approvals to send anything on Upwork or another real service. Session tokens, passwords and signing keys are not saved in the result JSON.", "",
             "## Observed checks", "", "| Check | Result |", "|---|---|"]
    for check in data["checks"]:
        lines.append(f"| {check['name']} | {'PASS' if check['passed'] else 'FAIL'} |")
    lines += ["", "## Defects exposed and corrected", "",
              "- API model errors emitted a failed SSE event while the run registry stayed running. The registry now persists the failed state.",
              "- Repeating a job start created another run. Identical requests now reuse the run; changed user settings can supersede an old analysis, whose stale approval is rejected.",
              "- User-edited experience claims bypassed grounding. Proposal and reply edits now receive grounding checks and cannot be approved while unsupported or only partly supported. Empty drafts are blocked.",
              "- The real liaison labelled a meeting request as negotiation and invented 2023 offered slots. Explicit meeting requests now route to the calendar; thread IDs and offered slots are owned by code and tool output.",
              "- A fixed historical calendar date could propose past interviews. The default now resolves today in Asia/Karachi; explicit fixed dates remain available for controlled simulations.",
              "- The real Critic accepted an under-length stress draft. Deterministic word-count and opener checks now supplement the real model's review. The final stress case actually re-enters the Writer and stops within two revisions.",
              "- The initial OCR stress draft included a partly supported experience claim. The old filter retained partly supported text; it now removes it rather than displaying it as verified. Model-authored logistics cannot bypass proposal grounding.", "",
              "## Concrete trace evidence", "", "| Scenario | Run / trace | Observed state |", "|---|---|---|"]
    for name in ("normal_proposal", "approved_proposal", "scam", "injection", "interview_reply", "approved_reply", "malicious_client_message", "critic_length_stress", "model_endpoint_unavailable"):
        case = data["cases"].get(name, {})
        run = case.get("run", {})
        lines.append(f"| {name} | `{run.get('run_id', 'n/a')}` / `{run.get('trace_id', 'n/a')}` | {run.get('status', 'n/a')} |")
    lines += ["", "The JSON contains node events, checkpoint summaries, model responses, mock marketplace audit entries, "
              "approval payloads and a claim-to-source matrix for the normal proposal. These are local trace records, not public LangSmith/Langfuse trace links.", "",
              "The configured Critic stress case executes actual revisions; reaching the retry cap is not a guarantee "
              "that the model satisfies every requested style constraint. Its final verdict remains visible in the approval payload.", ""]
    preview_file = results / "real_agent_live_preview.json"
    if preview_file.exists():
        preview = json.loads(preview_file.read_text())
        lines += ["## Live local demo", "",
                  f"The normal dataset launcher also generated job `{preview['job_id']}` as run `{preview['run_id']}` "
                  f"with trace `{preview['trace_id']}` at `{preview['live_api']}`. Its pending approval payload and "
                  "signed login session survived a real launcher/API restart using the persistent local state. "
                  "The draft was left awaiting human approval; no approval or send was issued in the live demo. "
                  "Evidence: `evals/results/real_agent_live_preview.json`.", ""]
    lines += ["## Limits", ""]
    lines += ["- " + limitation for limitation in data["limitations"]]
    lines += ["- The known scam/injection cases do not establish robustness against arbitrary unseen attacks.",
              "- Restart coverage is SQLite pending approval before any submission. The observed replay protections are not proof of Postgres/Redis or external-marketplace crash-after-send exactly-once behavior.",
              "- Claim filtering remains lexical. Passing citation and threshold checks does not establish complete semantic truth; calibrated semantic evaluation and human review remain outstanding.",
              "- The earlier two-model comparison is a historical snapshot before this guard hardening. Its latency and draft metrics are not a fresh benchmark of the updated revision.", "",
              "## Reproduce", "", "```bash", "python -m scripts.local_models",
              "python -m evals.runners.verify_real_agents --out evals/results/real_agent_behaviour.json",
              "python -m evals.analyze_real_agents", "```", "",
              "Each verifier run creates fresh isolated SQLite state under `.local-models/behavior-*`, chooses an unused loopback port, "
              "and stops its API processes afterward. It does not alter the live demo's runs or send real messages.", ""]
    output = root / "docs/REAL_AGENT_BEHAVIOUR.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
