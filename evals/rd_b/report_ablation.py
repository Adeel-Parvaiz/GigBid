"""Regenerate the R&D B ablation tables and downstream/calibration analysis."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from evals.rd_b.run_ablation import DEFAULT_OUTPUT, ROOT

RESULTS_PATH = DEFAULT_OUTPUT / "ablation_per_job.jsonl"
RUN_PATH = DEFAULT_OUTPUT / "ablation_run.json"
REPORT_PATH = ROOT / "docs" / "RD_B_ABLATION_RESULTS.md"
B4_ROWS_PATH = ROOT / "evals" / "results" / "b4_exploratory" / "runs.jsonl"
B4_SUMMARY_PATH = ROOT / "evals" / "results" / "b4_exploratory" / "summary.json"
FULL = "v1_v2_v3"
ABLATIONS = ("no_decomposition", "no_hybrid", "no_reranking")
REFERENCE = "v0_naive"
CONDITIONS = (REFERENCE, FULL, *ABLATIONS)
JOB_TYPES = ("normal", "scam", "injection")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _p95(values: list[float]) -> float | None:
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row["n_gold_sources"] > 0]
    return {
        "jobs": len(rows),
        "eligible_jobs": len(eligible),
        "recall@5": _mean([row["recall@5"] for row in eligible]),
        "ndcg@10": _mean([row["ndcg@10"] for row in eligible]),
        "empty_result_rate": _mean([float(row["empty_result"]) for row in rows]),
        "mean_returned_sources": _mean([float(row["returned_sources_at_10"]) for row in rows]),
        "p95_latency_ms": _p95([float(row["latency_ms"]) for row in rows]),
    }


def _bootstrap_ci(deltas: list[float], seed: int, resamples: int = 10_000) -> list[float] | None:
    if not deltas:
        return None
    values = np.asarray(deltas, dtype=np.float64)
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, len(values), size=(resamples, len(values)))
    means = values[samples].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def _job_type(row: dict[str, Any]) -> str:
    return row.get("job_type", "unknown")


def _build_summary(rows: list[dict[str, Any]], run_metadata: dict[str, Any]) -> dict[str, Any]:
    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_persona: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_category: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_persona_category: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    by_type: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_complexity: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_case: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        condition = row["condition"]
        if condition not in CONDITIONS:
            raise ValueError(f"Unexpected ablation condition: {condition}")
        by_condition[condition].append(row)
        by_persona[condition, row["persona"]].append(row)
        by_category[condition, row["job_category"]].append(row)
        by_persona_category[condition, row["persona"], row["job_category"]].append(row)
        by_type[condition, _job_type(row)].append(row)
        by_complexity[condition, "4+ requirements" if row["n_requirements"] >= 4 else "fewer than 4"].append(row)
        key = (condition, row["persona"] + "/" + row["job_id"])
        if key in by_case:
            raise ValueError(f"Duplicate row for {key}")
        by_case[key] = row

    all_case_ids = {case_id for condition, case_id in by_case if condition == FULL}
    for condition in CONDITIONS:
        if {case_id for name, case_id in by_case if name == condition} != all_case_ids:
            raise ValueError(f"Condition {condition} does not contain the same paired jobs")
        for case_id in all_case_ids:
            base = by_case[FULL, case_id]
            row = by_case[condition, case_id]
            if base["gold_source_ids"] != row["gold_source_ids"]:
                raise ValueError(f"Gold labels differ for paired case {case_id}")

    overall = {condition: _metrics(by_condition[condition]) for condition in CONDITIONS}
    by_persona_summary = {
        condition: {
            persona: _metrics(subset)
            for (name, persona), subset in sorted(by_persona.items())
            if name == condition
        }
        for condition in CONDITIONS
    }
    by_category_summary = {
        condition: {
            category: _metrics(subset)
            for (name, category), subset in sorted(by_category.items())
            if name == condition
        }
        for condition in CONDITIONS
    }
    by_persona_category_summary = {
        condition: {
            f"{persona} / {category}": _metrics(subset)
            for (name, persona, category), subset in sorted(by_persona_category.items())
            if name == condition
        }
        for condition in CONDITIONS
    }
    by_type_summary = {
        condition: {
            job_type: _metrics(by_type[condition, job_type])
            for job_type in JOB_TYPES
        }
        for condition in CONDITIONS
    }
    by_complexity_summary = {
        condition: {
            label: _metrics(by_complexity[condition, label])
            for label in ("4+ requirements", "fewer than 4")
        }
        for condition in CONDITIONS
    }

    full_rows = {
        (row["persona"], row["job_id"]): row
        for row in by_condition[FULL]
        if row["n_gold_sources"] > 0
    }
    reference_rows = {
        (row["persona"], row["job_id"]): row
        for row in by_condition[REFERENCE]
        if row["n_gold_sources"] > 0
    }
    if full_rows.keys() != reference_rows.keys():
        raise ValueError("Reference and full candidate have different eligible jobs")

    paired_deltas = {}
    for condition in (REFERENCE, *ABLATIONS):
        condition_rows = {
            (row["persona"], row["job_id"]): row
            for row in by_condition[condition]
            if row["n_gold_sources"] > 0
        }
        if condition_rows.keys() != full_rows.keys():
            raise ValueError(f"Condition {condition} has different eligible jobs")
        delta = [
            float(full_rows[key]["recall@5"]) - float(condition_rows[key]["recall@5"])
            for key in full_rows
        ]
        paired_deltas[condition] = {
            "n": len(delta),
            "full_minus_condition_recall@5": _mean(delta),
            "paired_bootstrap_95ci": _bootstrap_ci(delta, 4016),
        }

    primary_uplift = (
        overall[FULL]["recall@5"] - overall[REFERENCE]["recall@5"]
        if overall[FULL]["recall@5"] is not None and overall[REFERENCE]["recall@5"] is not None
        else None
    )
    high_req_delta = (
        by_complexity_summary[FULL]["4+ requirements"]["recall@5"]
        - by_complexity_summary[REFERENCE]["4+ requirements"]["recall@5"]
        if by_complexity_summary[FULL]["4+ requirements"]["recall@5"] is not None
        and by_complexity_summary[REFERENCE]["4+ requirements"]["recall@5"] is not None
        else None
    )
    ablation_drop = {
        name: paired_deltas[name]["full_minus_condition_recall@5"] for name in ABLATIONS
    }
    hypothesis = {
        "primary_full_minus_v0_at_least_0_10": primary_uplift is not None and primary_uplift >= 0.10,
        "each_component_ablation_drops_at_least_0_01": all(value is not None and value >= 0.01 for value in ablation_drop.values()),
        "component_ablation_drops": ablation_drop,
        "primary_recall_uplift": primary_uplift,
        "secondary_4plus_full_minus_v0_at_least_0_15": high_req_delta is not None and high_req_delta >= 0.15,
        "secondary_4plus_recall_uplift": high_req_delta,
        "secondary_4plus_eligible_jobs": by_complexity_summary[FULL]["4+ requirements"]["eligible_jobs"],
    }
    return {
        "experiment": run_metadata["experiment"],
        "created_at": run_metadata["created_at"],
        "preregistration": run_metadata["preregistration"],
        "dataset": run_metadata["dataset"],
        "configuration": run_metadata["configuration"],
        "conditions": overall,
        "by_persona": by_persona_summary,
        "by_job_category": by_category_summary,
        "by_persona_and_job_category": by_persona_category_summary,
        "by_synthetic_job_type": by_type_summary,
        "by_requirement_count": by_complexity_summary,
        "paired_recall_deltas": paired_deltas,
        "hypothesis": hypothesis,
        "limitations": run_metadata["limitations"],
    }


def _fmt(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _render_report(summary: dict[str, Any], b4_rows: list[dict[str, Any]], b4_summary: dict[str, Any]) -> str:
    lines = [
        "# R&D B — preregistered component ablation",
        "",
        f"**Run:** `{summary['created_at']}`. **Data:** synthetic jobs, portfolios, and rule-derived evidence labels only. "
        "The preregistration followed inspection of earlier exploratory results; this is not an independent replication. "
        f"Protocol: [{Path(summary['preregistration']).name}](RD_B_PREREGISTRATION.md). Dataset provenance: [DATA_CARD.md](DATA_CARD.md).",
        "",
        "## Hypothesis and result",
        "",
        "Before this run, we predicted that the complete V1 decomposition + V2 dense/BM25 hybrid + V3 cross-encoder "
        "pipeline would beat V0 by at least 0.10 absolute Recall@5 on evidence-positive jobs, that each one-component "
        "ablation would reduce Recall@5 by at least 0.01, and that the full pipeline would beat V0 by at least 0.15 "
        "on evidence-positive jobs with four or more required skills.",
        "",
        "The ablation runner explicitly selected FastEmbed for both embeddings and the cross-encoder. The earlier "
        "`run_real_embedder.py` composite used the checked-in config's lexical reranker default; therefore its "
        "composite score is not a same-model baseline for this run. All ablation comparisons below keep the "
        "actual cross-encoder fixed except in the `no_reranking` condition.",
        "",
        f"- Full-vs-V0 Recall@5 uplift: **{_fmt(summary['hypothesis']['primary_recall_uplift'])}**; "
        f"0.10 threshold: **{'met' if summary['hypothesis']['primary_full_minus_v0_at_least_0_10'] else 'not met'}**.",
        f"- Every component removal drops Recall@5 by at least 0.01: "
        f"**{'yes' if summary['hypothesis']['each_component_ablation_drops_at_least_0_01'] else 'no'}**.",
        f"- 4+ requirements uplift: **{_fmt(summary['hypothesis']['secondary_4plus_recall_uplift'])}** "
        f"(n={summary['hypothesis']['secondary_4plus_eligible_jobs']}); 0.15 threshold: "
        f"**{'met' if summary['hypothesis']['secondary_4plus_full_minus_v0_at_least_0_15'] else 'not met'}**.",
        "",
        "## Aggregate retrieval results",
        "",
        "Recall@5 and nDCG@10 are averaged over cases with nonempty synthetic source-evidence gold. "
        "All 600 job-persona cases are retained for refusal/empty-result and latency reporting. "
        "Confidence intervals on full-minus-condition Recall@5 are paired bootstrap intervals (10,000 resamples, "
        "seed 4016); they are descriptive and not used as significance tests.",
        "",
        "| Condition | Jobs (eligible) | Recall@5 | nDCG@10 | Empty result rate | p95 ms | Δ Recall@5 vs full (95% paired CI) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        metric = summary["conditions"][condition]
        delta = summary["paired_recall_deltas"].get(condition)
        delta_text = "reference" if condition == FULL else "n/a"
        if delta:
            interval = delta["paired_bootstrap_95ci"]
            delta_text = f"{_fmt(delta['full_minus_condition_recall@5'])} [{_fmt(interval[0])}, {_fmt(interval[1])}]"
        lines.append(
            f"| `{condition}` | {metric['jobs']} ({metric['eligible_jobs']}) | {_fmt(metric['recall@5'], 4)} "
            f"| {_fmt(metric['ndcg@10'], 4)} | {_fmt(metric['empty_result_rate'] * 100 if metric['empty_result_rate'] is not None else None, 1)}% "
            f"| {_fmt(metric['p95_latency_ms'], 1)} | {delta_text} |"
        )
    lines.extend(["", "## Persona breakdown", "",
                  "| Condition | Persona | Jobs (eligible) | Recall@5 | nDCG@10 | Empty result rate |",
                  "|---|---|---:|---:|---:|---:|"])
    for condition in CONDITIONS:
        for persona, metric in summary["by_persona"][condition].items():
            empty = metric["empty_result_rate"] * 100 if metric["empty_result_rate"] is not None else None
            lines.append(
                f"| `{condition}` | {persona} | {metric['jobs']} ({metric['eligible_jobs']}) "
                f"| {_fmt(metric['recall@5'], 4)} | {_fmt(metric['ndcg@10'], 4)} | {_fmt(empty, 1)}% |"
            )
    lines.extend(["", "## Job category breakdown", "",
                  "`job_category` is the synthetic corpus category (not a human-verified occupation label). "
                  "Cells with no evidence-positive cases report n/a for evidence metrics.",
                  "",
                  "| Condition | Job category | Jobs (eligible) | Recall@5 | nDCG@10 | Empty result rate |",
                  "|---|---|---:|---:|---:|---:|"])
    for condition in CONDITIONS:
        for category, metric in summary["by_job_category"][condition].items():
            empty = metric["empty_result_rate"] * 100 if metric["empty_result_rate"] is not None else None
            lines.append(
                f"| `{condition}` | {category} | {metric['jobs']} ({metric['eligible_jobs']}) "
                f"| {_fmt(metric['recall@5'], 4)} | {_fmt(metric['ndcg@10'], 4)} | {_fmt(empty, 1)}% |"
            )
    lines.extend(["", "## Persona × job category", "",
                  "| Condition | Persona / category | Jobs (eligible) | Recall@5 | nDCG@10 |",
                  "|---|---|---:|---:|---:|"])
    for condition in CONDITIONS:
        for persona_category, metric in summary["by_persona_and_job_category"][condition].items():
            lines.append(
                f"| `{condition}` | {persona_category} | {metric['jobs']} ({metric['eligible_jobs']}) "
                f"| {_fmt(metric['recall@5'], 4)} | {_fmt(metric['ndcg@10'], 4)} |"
            )
    lines.extend(["", "## Synthetic safety-type breakdown", "",
                  "Correction to the preregistration's data-stratum expectation: 22 scam and 16 injection rows "
                  "had nonempty synthetic evidence gold. Their retrieval scores are included over those eligible "
                  "rows. Recall/nDCG are undefined only for rows with no gold; the table gives eligible counts "
                  "and empty-result rates.",
                  "",
                  "| Condition | Type | Jobs | Eligible evidence jobs | Recall@5 | Empty result rate | Mean returned sources |",
                  "|---|---|---:|---:|---:|---:|---:|"])
    for condition in CONDITIONS:
        for job_type, metric in summary["by_synthetic_job_type"][condition].items():
            empty = metric["empty_result_rate"] * 100 if metric["empty_result_rate"] is not None else None
            lines.append(
                f"| `{condition}` | {job_type} | {metric['jobs']} | {metric['eligible_jobs']} "
                f"| {_fmt(metric['recall@5'], 4)} | {_fmt(empty, 1)}% | {_fmt(metric['mean_returned_sources'], 2)} |"
            )
    lines.extend(["", "## Did retrieval improvement translate to replies?", "",
                  "No measurable increase appeared in the existing B4 V0/V8 exploratory comparison: the B2 neural "
                  "retrieval benchmark reported V0 Recall@5/nDCG@10 of 0.2600/0.4700 and V8 of 0.3510/0.5792, "
                  "while B4 recorded 18/37 (48.6%) versus 17/35 (48.6%) simulated replies per submitted proposal. "
                  "These are different cohorts and variants; this is not a paired causal test, and it does not "
                  "establish that retrieval has no effect.",
                  "",
                  "The project-owned `LocalSimAdapter` computes reply probability from required-skill mentions in "
                  "the proposal text, bid amount versus a hidden ceiling, title-word personalization, and a generic-opening "
                  "penalty. It does not reward Recall@5 or evidence rank directly. Retrieval can therefore improve "
                  "without changing the drafted wording, affordability, personalization, or whether the proposal passes "
                  "submission gates. Only submitted proposals enter the reply denominator; small denominators and "
                  "rule-derived synthetic outcomes further limit the comparison.",
                  "",
                  "| B4 variant | Persona | Type | Submitted with matched outcome | Replies | Reply rate |"])
    lines.append("|---|---|---|---:|---:|---:|")
    b4_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in b4_rows:
        variant = row.get("variant")
        if variant not in {"v0_naive", "v8_corrective"}:
            continue
        gold = row.get("gold") or {}
        job_type = "scam" if gold.get("scam") else "injection" if gold.get("injection") else "normal"
        b4_groups[variant, row.get("persona", "unknown"), job_type].append(row)
    for key in sorted(b4_groups):
        submitted = [
            row for row in b4_groups[key]
            if row.get("submitted") and row.get("outcome_match") == "draft_id" and isinstance(row.get("outcome"), dict)
        ]
        replies = sum(bool(row["outcome"].get("replied")) for row in submitted)
        rate = replies / len(submitted) if submitted else None
        lines.append(
            f"| `{key[0]}` | {key[1]} | {key[2]} | {len(submitted)} | {replies} | "
            f"{'n/a' if rate is None else f'{rate:.1%}'} |"
        )
    calibration = b4_summary.get("calibration", {})
    lines.extend([
        "",
        "## Judge calibration",
        "",
        f"The existing proposal judge calibration used **{calibration.get('n', 0)}** author-labeled items; "
        f"agreement was **{(calibration.get('agreement') or 0) * 100:.1f}%** and unweighted Cohen's κ was "
        f"**{_fmt(calibration.get('kappa'))}** (status: `{calibration.get('status', 'unknown')}`). "
        "With κ=0, rubric scores are not calibrated and are not used to select the retrieval variant. "
        f"The blind classmate panel remains `{b4_summary.get('panel', {}).get('status', 'unknown')}`.",
        "",
        "## Shipping decision",
        "",
        "Keep `v1_decomposed` as the configured shipping variant. The combined V1+V2+V3 candidate and its "
        "one-factor ablations are development-only: even a retrieval win is not a demonstrated improvement in "
        "human-rated proposal quality or client replies, and the available GigSim reply rates did not rise from "
        "V0 to V8. The local judge has κ=0, the outcomes are synthetic, and the new ablation has no independent "
        "instructor labels. Reconsider shipping only after matched proposal/outcome evaluation and usable human "
        "calibration; do not promote the composite solely on Recall@5.",
        "",
        "## Reproduction and artifacts",
        "",
        "- Run the frozen retrieval experiment: `python -m evals.rd_b.run_ablation`.",
        "- Regenerate this report/table from saved run artifacts: `python -m evals.rd_b.report_ablation`.",
        "- Variant composition: `evals/rd_b/ablation_variants.py`; raw per-job rows: `evals/rd_b/results/ablation_per_job.jsonl`; model/data manifest: `evals/rd_b/results/ablation_run.json`; summarized metrics: `evals/rd_b/results/ablation_summary.json`.",
        "- Prior B2/B4 results and calibration inputs are retained separately; see `evals/results/b2/summary.json`, `evals/results/b4_exploratory/summary.json`, `agent/config.yaml`, and `docs/DATA_CARD.md`.",
        "",
    ])
    return "\n".join(lines)


def generate(
    results_path: Path = RESULTS_PATH,
    run_path: Path = RUN_PATH,
    b4_rows_path: Path = B4_ROWS_PATH,
    b4_summary_path: Path = B4_SUMMARY_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    rows = _read_jsonl(results_path)
    run_metadata = json.loads(run_path.read_text(encoding="utf-8"))
    b4_rows = _read_jsonl(b4_rows_path)
    b4_summary = json.loads(b4_summary_path.read_text(encoding="utf-8"))
    summary = _build_summary(rows, run_metadata)
    summary["b4_calibration"] = b4_summary.get("calibration", {})
    summary["b4_panel"] = b4_summary.get("panel", {})
    (run_path.parent / "ablation_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(summary, b4_rows, b4_summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--run-metadata", type=Path, default=RUN_PATH)
    parser.add_argument("--b4-rows", type=Path, default=B4_ROWS_PATH)
    parser.add_argument("--b4-summary", type=Path, default=B4_SUMMARY_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    summary = generate(args.results, args.run_metadata, args.b4_rows, args.b4_summary, args.report)
    print(json.dumps({"conditions": summary["conditions"], "hypothesis": summary["hypothesis"]}, indent=2))


if __name__ == "__main__":
    main()
