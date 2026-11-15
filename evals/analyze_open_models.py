"""Build a report table from completed real-model comparison results."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def display(value):
    if value is None:
        return "n/a"
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="evals/results/open_model_comparison.json")
    parser.add_argument("--output", default="docs/OPEN_MODEL_RESULTS.md")
    args = parser.parse_args()
    source = Path(args.input)
    result = json.loads(source.read_text())
    if result["status"] != "completed":
        raise SystemExit("Comparison has not completed; refusing to publish a final results table")
    meta = result["meta"]
    def rank(model):
        s = result["summaries"][model]["all"]
        quality = ((s["bid_f1_completed"]["f1"] or 0) + (s["scam_detection_completed"]["f1"] or 0)) / 2
        return (s["completion_rate"] or 0, quality, s["accuracy_including_errors"] or 0,
                -(s["unsupported_after_per_draft"] if s["unsupported_after_per_draft"] is not None else float("inf")),
                -(s["latency_seconds_p95"] or float("inf")))

    chosen = max(meta["models"], key=rank)
    started = datetime.fromisoformat(result["started_at_utc"]).astimezone(ZoneInfo("Asia/Karachi")).strftime("%Y-%m-%d %H:%M:%S PKT")
    finished = datetime.fromisoformat(result["finished_at_utc"]).astimezone(ZoneInfo("Asia/Karachi")).strftime("%Y-%m-%d %H:%M:%S PKT")
    text = ["# Real open-model comparison results", "",
            f"Source: `{source.as_posix()}`. Started {started}; finished {finished}. Raw timestamps remain UTC in the JSON.", "",
            f"Two real open-weight models, {meta['dev_per_persona']} identical seeded jobs per persona per model, seed {meta['seed']}. "
            f"Excluded {len(meta['excluded_pilot_jobs'])} persona/job pairs used in the initial prompt-development pilot. "
            "Gold labels are synthetic/rule-derived. This is not the full 200-job-per-persona set or an instructor evaluation.", "",
            f"Hardware: {meta['hardware']}. Endpoint: `{meta['endpoint']}`. Runtime/model digests: `evals/results/open_model_runtime.json`.", "",
            "Runtime aliases: `qwen25-15b` = Qwen2.5 1.5B Q4_K_M; `qwen25-05b` = Qwen2.5 0.5B Q4_K_M.", "",
            "Both conditions hold prompts, graph, retrieval and verifier constant. All LLM roles use the listed model. "
            "The graph stops at human approval; proposals are not submitted. The risk prompt was calibrated with safe/unsafe examples after "
            "a 1.5B pilot incorrectly flagged a normal project as injection. Pilot attempts and diagnostic outputs remain in "
            "`evals/results/open_model_initial_partial.json` and `evals/results/open_model_risk_probe.json`.", "",
            "| Model | Completed/attempted | Accuracy incl. errors | Bid F1 (completed) | Scam F1 (completed) | Drafts | Unsupported before/after per draft | p50/p95 seconds | Input/output tokens | API USD |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for model in meta["models"]:
        s = result["summaries"][model]["all"]
        text.append(f"| {model} | {s['completed']}/{s['attempted']} | {display(s['accuracy_including_errors'])} | "
                    f"{display(s['bid_f1_completed']['f1'])} | {display(s['scam_detection_completed']['f1'])} | {s['drafts']} | "
                    f"{display(s['unsupported_before_per_draft'])}/{display(s['unsupported_after_per_draft'])} | "
                    f"{display(s['latency_seconds_p50'])}/{display(s['latency_seconds_p95'])} | "
                    f"{display(s['prompt_tokens'])}/{display(s['completion_tokens'])} | {display(meta['api_cost_usd'])} |")
    text += ["", "| Model | Persona | Accuracy incl. errors | Bid F1 | Scam recall | Fair-price-band rate | p95 seconds |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for model in meta["models"]:
        for persona, s in result["summaries"][model]["personas"].items():
            text.append(f"| {model} | {persona} | {display(s['accuracy_including_errors'])} | "
                        f"{display(s['bid_f1_completed']['f1'])} | {display(s['scam_detection_completed']['recall'])} | "
                        f"{display(s['price_in_band_rate'])} | {display(s['latency_seconds_p95'])} |")
    text += ["", "| Model | Tokens/job | Completion tokens/HTTP second | Draft-job p95 seconds |",
             "|---|---:|---:|---:|"]
    for model in meta["models"]:
        s = result["summaries"][model]["all"]
        text.append(f"| {model} | {display(s['tokens_per_job'])} | {display(s['completion_tokens_per_http_second'])} | {display(s['draft_job_seconds_p95'])} |")
    mistakes = [r for r in result["rows"] if not r["completed"] or r.get("action") != r["gold"]]
    text += ["", "The smaller model's higher observed completion throughput did not produce faster jobs. "
             "Its repeated invalid/truncated JSON consumed tokens and repair attempts; compare token totals, completion coverage and end-to-end latency together. "
             "Throughput here includes HTTP overhead and is not a pure decoder benchmark."]
    text += ["", f"## Observed decision/execution failures ({len(mistakes)})", "",
             "Examples below are actual saved cases, not invented labels. Gold is still synthetic.", "",
             "| Model | Persona | Job | Gold | Model action/error |", "|---|---|---|---|---|"]
    for row in mistakes[:10]:
        text.append(f"| {row['model']} | {row['persona']} | {row['job_id']} | {row['gold']} | {row.get('action', row.get('error_type'))} |")
    text += ["", "## Limitations", "", "- " + meta["cost_note"],
             "- This is a small development subset following a prompt-development pilot; no significance or generalization claim is made.",
             "- Reported claim support is the lexical verifier's assessment of the final draft pass; it is not human verification.",
             "- Failure rates and null metrics are retained. F1 on completed jobs excludes errors; accuracy including errors penalizes them.",
             "- Latency includes cold loading, queueing and schema-repair calls. Token totals include recorded repairs.",
             "- No calibrated judge, human panel, GigSim outcome or live marketplace outcome was evaluated.", ""]
    text += ["## Local configuration choice", "",
             f"Selected `{chosen}` for this local comparison. Selection prioritizes completion rate, then mean bid/scam F1, "
             "then accuracy including errors, fewer final unsupported claims, and lower p95 latency. "
             "This is a development choice from a small subset, not a production-quality certification.", ""]
    selection = {"selected_model_alias": chosen, "source": str(source), "selection_rule":
                 "completion rate, mean bid/scam F1, accuracy incl errors, fewer unsupported final claims, lower p95 latency"}
    source.with_name("open_model_selection.json").write_text(json.dumps(selection, indent=2))
    Path(args.output).write_text("\n".join(text), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
