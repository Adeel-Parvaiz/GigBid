"""Analyze R&D B retrieval and downstream decision results.

Run after `python -m evals.rd_b.run_real_embedder`:
    python -m evals.rd_b.analyze_retrieval
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

from evals.rd_b.run_real_embedder import (
    AGGREGATE_RESULTS,
    DECISION_RESULTS,
    DECISION_VARIANTS,
    EMBEDDERS,
    RESULTS_DIR,
    RETRIEVAL_RESULTS,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "docs" / "RD_B_RESULTS.md"
CHART_PATH = RESULTS_DIR / "comparison.svg"
EMBEDDER_LABELS = {"hashing": "Hashing baseline", "fastembed": "FastEmbed open model"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _p95(values: list[float]) -> float | None:
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None


def _percent(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "n/a"


def _retrieval_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("No retrieval rows to summarize")
    total_relevant = sum(row["n_relevant_evidence"] for row in rows)
    return {
        "n_queries": len(rows),
        "recall@5": _mean([row["recall@5"] for row in rows]),
        "mrr": _mean([row["mrr"] for row in rows]),
        "ndcg@10": _mean([row["ndcg@10"] for row in rows]),
        "relevant_evidence_recall@5_micro": (
            sum(row["relevant_evidence_retrieved_at_5"] for row in rows) / total_relevant if total_relevant else None
        ),
        "relevant_evidence_retrieved_at_5": sum(row["relevant_evidence_retrieved_at_5"] for row in rows),
        "relevant_evidence_retrieved_at_10": sum(row["relevant_evidence_retrieved_at_10"] for row in rows),
        "relevant_evidence_total": total_relevant,
        "latency_ms_median": statistics.median([row["latency_ms"] for row in rows]),
        "latency_ms_p95": _p95([row["latency_ms"] for row in rows]),
    }


def _decision_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("No decision rows to summarize")
    true_positive = sum(row["action"] == row["gold_action"] == "bid" for row in rows)
    false_positive = sum(row["action"] == "bid" and row["gold_action"] == "skip" for row in rows)
    false_negative = sum(row["action"] == "skip" and row["gold_action"] == "bid" for row in rows)
    true_negative = sum(row["action"] == row["gold_action"] == "skip" for row in rows)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else None
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else None
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else 0.0
    labels = [label for row in rows for label in row["claim_verdicts"]]
    counts = {label: sum(item["label"] == label for item in labels)
              for label in ("supported", "partly_supported", "unsupported")}
    total = sum(counts.values())
    return {
        "n_jobs": len(rows),
        "accuracy": (true_positive + true_negative) / len(rows),
        "bid_precision": precision,
        "bid_recall": recall,
        "bid_f1": f1,
        "confusion": {
            "true_positive_bid": true_positive,
            "false_positive_bid": false_positive,
            "false_negative_bid": false_negative,
            "true_negative_skip": true_negative,
        },
        "claims_evaluated": total,
        "claim_verdict_counts": counts,
        "claim_verdict_rates": {label: count / total if total else None for label, count in counts.items()},
        "graph_latency_ms_median": statistics.median([row["latency_ms"] for row in rows]),
        "graph_latency_ms_p95": _p95([row["latency_ms"] for row in rows]),
    }


def _paired_analysis(retrieval_rows: list[dict[str, Any]], decision_rows: list[dict[str, Any]]) -> dict[str, Any]:
    retrieval = {
        (row["persona"], row["variant"], row["job_id"], row["embedder"]): row for row in retrieval_rows
    }
    decisions = {
        (row["persona"], row["variant"], row["job_id"], row["embedder"]): row for row in decision_rows
    }

    def summarize(variant: str) -> dict[str, Any]:
        pairs = []
        for (persona, retrieval_variant, job_id, embedder), real_row in retrieval.items():
            if embedder != "fastembed" or retrieval_variant != variant:
                continue
            baseline = retrieval[(persona, retrieval_variant, job_id, "hashing")]
            base_decision = decisions[(persona, variant, job_id, "hashing")]
            real_decision = decisions[(persona, variant, job_id, "fastembed")]
            pairs.append({
                "persona": persona,
                "job_id": job_id,
                "recall_delta": real_row["recall@5"] - baseline["recall@5"],
                "mrr_delta": real_row["mrr"] - baseline["mrr"],
                "ndcg_delta": real_row["ndcg@10"] - baseline["ndcg@10"],
                "baseline_action": base_decision["action"],
                "fastembed_action": real_decision["action"],
                "baseline_correct": base_decision["decision_correct"],
                "fastembed_correct": real_decision["decision_correct"],
            })
        if not pairs:
            raise ValueError(f"No paired {variant} retrieval and decision rows found")
        improved_no_decision_gain = [
            row for row in pairs if row["recall_delta"] > 0 and row["baseline_correct"] == row["fastembed_correct"]
        ]
        improved_but_wrong = [row for row in improved_no_decision_gain if not row["fastembed_correct"]]
        retrieval_drop_decision_harm = [
            row for row in pairs if row["recall_delta"] < 0 and row["baseline_correct"] and not row["fastembed_correct"]
        ]
        decision_improvement_with_retrieval_drop = [
            row for row in pairs if row["recall_delta"] < 0 and not row["baseline_correct"] and row["fastembed_correct"]
        ]
        action_change_no_accuracy_change = [
            row for row in pairs if row["baseline_action"] != row["fastembed_action"]
            and row["baseline_correct"] == row["fastembed_correct"]
        ]
        by_persona = {}
        for persona in sorted({row["persona"] for row in pairs}):
            subset = [row for row in pairs if row["persona"] == persona]
            by_persona[persona] = {
                "n_paired_jobs": len(subset),
                "recall_improved": sum(row["recall_delta"] > 0 for row in subset),
                "recall_decreased": sum(row["recall_delta"] < 0 for row in subset),
                "decision_action_changed": sum(row["baseline_action"] != row["fastembed_action"] for row in subset),
                "decision_correctness_improved": sum(not row["baseline_correct"] and row["fastembed_correct"] for row in subset),
                "decision_correctness_decreased": sum(row["baseline_correct"] and not row["fastembed_correct"] for row in subset),
            }
        base_accuracy = sum(row["baseline_correct"] for row in pairs) / len(pairs)
        fast_accuracy = sum(row["fastembed_correct"] for row in pairs) / len(pairs)
        return {
            "n_paired_jobs": len(pairs),
            "decision_accuracy_baseline_on_paired_jobs": base_accuracy,
            "decision_accuracy_fastembed_on_paired_jobs": fast_accuracy,
            "decision_accuracy_delta_on_paired_jobs": fast_accuracy - base_accuracy,
            "recall_improved": sum(row["recall_delta"] > 0 for row in pairs),
            "recall_unchanged": sum(row["recall_delta"] == 0 for row in pairs),
            "recall_decreased": sum(row["recall_delta"] < 0 for row in pairs),
            "decision_action_changed": sum(row["baseline_action"] != row["fastembed_action"] for row in pairs),
            "decision_correctness_improved": sum(not row["baseline_correct"] and row["fastembed_correct"] for row in pairs),
            "decision_correctness_decreased": sum(row["baseline_correct"] and not row["fastembed_correct"] for row in pairs),
            "recall_improved_but_decision_correctness_unchanged": len(improved_no_decision_gain),
            "recall_improved_but_decision_still_incorrect": len(improved_but_wrong),
            "retrieval_decreased_and_decision_correctness_decreased": len(retrieval_drop_decision_harm),
            "retrieval_decreased_but_decision_correctness_improved": len(decision_improvement_with_retrieval_drop),
            "action_changed_without_correctness_change": len(action_change_no_accuracy_change),
            "by_persona": by_persona,
            "examples_recall_improved_no_correctness_gain": [
                {"variant": variant, **{k: row[k] for k in (
                    "persona", "job_id", "recall_delta", "baseline_action", "fastembed_action",
                    "baseline_correct", "fastembed_correct")}}
                for row in improved_no_decision_gain[:10]
            ],
            "examples_retrieval_decrease_with_decision_harm": [
                {"variant": variant, **{k: row[k] for k in (
                    "persona", "job_id", "recall_delta", "baseline_action", "fastembed_action",
                    "baseline_correct", "fastembed_correct")}}
                for row in retrieval_drop_decision_harm[:10]
            ],
            "examples_retrieval_decrease_but_decision_improved": [
                {"variant": variant, **{k: row[k] for k in (
                    "persona", "job_id", "recall_delta", "baseline_action", "fastembed_action",
                    "baseline_correct", "fastembed_correct")}}
                for row in decision_improvement_with_retrieval_drop[:10]
            ],
        }

    by_variant = {variant: summarize(variant) for variant in DECISION_VARIANTS}
    return {"primary_variant": DECISION_VARIANTS[0], "by_variant": by_variant}


def _svg(retrieval: dict[str, dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> str:
    variants = list(retrieval["hashing"])
    width, height = 1000, 480
    left, top, chart_height = 70, 80, 300
    bar_width = 25
    x_start = 100
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#222}.title{font-size:20px;font-weight:bold}.label{font-size:12px}.small{font-size:10px}</style>',
        '<text x="20" y="30" class="title">Hashing baseline vs local FastEmbed — synthetic evaluation</text>',
        f'<text x="{left}" y="62" class="label">Recall@5 by RAG variant</text>',
        f'<line x1="{left}" y1="{top + chart_height}" x2="970" y2="{top + chart_height}" stroke="#777"/>',
    ]
    per_variant = 112
    for i, variant in enumerate(variants):
        x = x_start + i * per_variant
        for j, condition in enumerate(("hashing", "fastembed")):
            value = retrieval[condition][variant]["recall@5"]
            bar_h = chart_height * value
            bx = x + j * (bar_width + 5)
            color = "#4c78a8" if condition == "hashing" else "#54a24b"
            svg.append(f'<rect x="{bx}" y="{top + chart_height - bar_h:.1f}" width="{bar_width}" height="{bar_h:.1f}" fill="{color}"/>')
            svg.append(f'<text x="{bx + bar_width / 2}" y="{top + chart_height - bar_h - 5:.1f}" text-anchor="middle" class="small">{value:.2f}</text>')
        svg.append(f'<text x="{x + bar_width}" y="{top + chart_height + 18}" text-anchor="middle" class="small">{variant}</text>')
    svg.extend([
        '<rect x="690" y="54" width="12" height="12" fill="#4c78a8"/><text x="708" y="64" class="small">Hashing</text>',
        '<rect x="785" y="54" width="12" height="12" fill="#54a24b"/><text x="803" y="64" class="small">FastEmbed</text>',
        '<text x="70" y="425" class="label">Decision accuracy (v1_decomposed, all personas)</text>',
        '<line x1="70" y1="440" x2="970" y2="440" stroke="#777"/>',
    ])
    for i, condition in enumerate(("hashing", "fastembed")):
        value = decisions[condition]["v1_decomposed"]["overall"]["accuracy"]
        x = 340 + i * 150
        bar_h = 90 * value
        color = "#4c78a8" if condition == "hashing" else "#54a24b"
        svg.append(f'<rect x="{x}" y="{440 - bar_h:.1f}" width="48" height="{bar_h:.1f}" fill="{color}"/>')
        svg.append(f'<text x="{x + 24}" y="{432 - bar_h:.1f}" text-anchor="middle" class="small">{value:.1%}</text>')
        svg.append(f'<text x="{x + 24}" y="458" text-anchor="middle" class="small">{condition}</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def _report(result: dict[str, Any]) -> str:
    retrieval, decisions = result["retrieval"], result["decisions"]
    variants = result["configuration"]["retrieval_variants"]
    rows = [
        "# R&D B — Real Embedding Model Evaluation",
        "",
        "> **Synthetic/local evaluation only.** The instructor development dataset is not present. "
        "The dev jobs are generated synthetic text with rule-derived labels; portfolio evidence and freelancer profiles are generated. "
        "No result here is evidence of real marketplace performance.",
        "",
        "## Setup and reproducibility",
        "",
        f"- Corpus: `{result['dataset']['data_dir']}`; processed corpus manifest SHA-256 `{result['dataset']['manifest_sha256']}`; "
        f"corpus build seed `{result['dataset']['manifest_seed']}`.",
        f"- Evaluation seed: `{result['seed']}`. Evaluation uses the same jobs and evidence IDs under both embedder conditions.",
        f"- Synthetic dev examples: {', '.join(f'{name}: {count}' for name, count in result['dataset']['dev_jobs_per_persona'].items())}; "
        f"label provenance `{', '.join(sorted({label for labels in result['dataset']['dev_label_provenance'].values() for label in labels}))}`. "
        "Gold is synthetic/rule-derived, not human-labelled.",
        f"- Baseline: {result['configuration']['baseline']}. Real open embedder: "
        f"`{result['configuration']['real_embedder']['model']}` via FastEmbed "
        f"{result['configuration']['real_embedder']['package_version']}, source "
        f"`{result['configuration']['real_embedder']['source']}`, revision "
        f"`{result['configuration']['real_embedder']['revision']}`, "
        f"model-file SHA-256 `{result['configuration']['real_embedder']['model_file_sha256']}`, "
        f"{result['configuration']['real_embedder']['dimensions']} dimensions, "
        f"license `{result['configuration']['real_embedder']['license']}`.",
        f"- Vector index: {result['configuration']['vector_index']}. All {result['configuration']['real_embedder']['corpus_items_reembedded']} "
        "portfolio evidence records were embedded again for each condition. Saved vector files and hashes are listed in `evals/rd_b/results/results.json`.",
        f"- Retrieval latency includes per-query embedding and search, but not one-time index construction; index build times are separately recorded. "
        f"RAG variants: {', '.join(variants)}. Decision graph variants: "
        f"`{', '.join(result['configuration']['decision_variants'])}` with "
        f"`{result['configuration']['decision_llm']}` and the existing lexical claim verifier.",
        "",
        "## Retrieval results",
        "",
        "| Variant | Queries | Hash Recall@5 | FastEmbed Recall@5 | Δ | Hash MRR | FastEmbed MRR | Δ | Hash nDCG@10 | FastEmbed nDCG@10 | Hash median ms | FastEmbed median ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in variants:
        base, real = retrieval["hashing"][variant], retrieval["fastembed"][variant]
        rows.append(
            f"| `{variant}` | {real['n_queries']} | {base['recall@5']:.4f} | {real['recall@5']:.4f} | "
            f"{real['recall@5'] - base['recall@5']:+.4f} | {base['mrr']:.4f} | {real['mrr']:.4f} | "
            f"{real['mrr'] - base['mrr']:+.4f} | {base['ndcg@10']:.4f} | {real['ndcg@10']:.4f} | "
            f"{base['latency_ms_median']:.3f} | {real['latency_ms_median']:.3f} |"
        )
    rows.extend(["", "![Embedding comparison](../evals/rd_b/results/comparison.svg)", "",
                 "### Retrieved relevant evidence and latency", "",
                 "| Embedder | v1 relevant evidence retrieved @5 / relevant total | Recall@5 micro | Median query latency (ms) | P95 query latency (ms) |",
                 "|---|---:|---:|---:|---:|"])
    for condition in EMBEDDERS:
        v1 = retrieval[condition]["v1_decomposed"]
        rows.append(
            f"| {EMBEDDER_LABELS[condition]} | {v1['relevant_evidence_retrieved_at_5']}/{v1['relevant_evidence_total']} | "
            f"{v1['relevant_evidence_recall@5_micro']:.4f} | {v1['latency_ms_median']:.3f} | {v1['latency_ms_p95']:.3f} |"
        )
    rows.extend(["", "## Downstream bid/skip and claim checks", "",
                 "| Decision variant | Persona | Embedder | N | Accuracy | Bid F1 | Bid precision | Bid recall | Supported claims | Partly supported | Unsupported | Graph median ms |",
                 "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    decision_variants = result["configuration"]["decision_variants"]
    for variant in decision_variants:
        for persona in result["dataset"]["dev_jobs_per_persona"]:
            for condition in EMBEDDERS:
                metric = decisions[condition][variant]["by_persona"][persona]
                rates = metric["claim_verdict_rates"]
                rows.append(
                    f"| `{variant}` | {persona} | {EMBEDDER_LABELS[condition]} | {metric['n_jobs']} | "
                    f"{metric['accuracy']:.1%} | {metric['bid_f1']:.4f} | {_percent(metric['bid_precision'])} | "
                    f"{_percent(metric['bid_recall'])} | {_percent(rates['supported'])} | "
                    f"{_percent(rates['partly_supported'])} | {_percent(rates['unsupported'])} | "
                    f"{metric['graph_latency_ms_median']:.2f} |"
                )
        for condition in EMBEDDERS:
            metric = decisions[condition][variant]["overall"]
            rates = metric["claim_verdict_rates"]
            rows.append(
                f"| `{variant}` | **All personas** | **{EMBEDDER_LABELS[condition]}** | **{metric['n_jobs']}** | "
                f"**{metric['accuracy']:.1%}** | **{metric['bid_f1']:.4f}** | "
                f"**{_percent(metric['bid_precision'])}** | **{_percent(metric['bid_recall'])}** | "
                f"**{_percent(rates['supported'])}** | **{_percent(rates['partly_supported'])}** | "
                f"**{_percent(rates['unsupported'])}** | **{metric['graph_latency_ms_median']:.2f}** |"
            )
    rows.extend(["", "### Paired results by persona (v1_decomposed)", "",
             "| Persona | Paired jobs | Recall@5 improved | Recall@5 decreased | Decisions changed | Decision correctness improved | Decreased |",
             "|---|---:|---:|---:|---:|---:|---:|"])
    for persona, metric in result["paired_v1_job_analysis"]["by_persona"].items():
        rows.append(
            f"| {persona} | {metric['n_paired_jobs']} | {metric['recall_improved']} | {metric['recall_decreased']} | "
            f"{metric['decision_action_changed']} | {metric['decision_correctness_improved']} | "
            f"{metric['decision_correctness_decreased']} |"
        )
    rows.extend([
        "",
        "### Paired downstream comparison by decision variant",
        "",
        "This subset contains only job/persona rows with at least one gold evidence item and matches the retrieval variant to the decision variant.",
        "",
        "| Variant | Paired rows | Hash accuracy | FastEmbed accuracy | Δ accuracy | Recall improved | Recall decreased | Improved recall, unchanged correctness | Recall drop with correctness drop |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for variant, metric in result["paired_decision_analysis"]["by_variant"].items():
        rows.append(
            f"| `{variant}` | {metric['n_paired_jobs']} | "
            f"{metric['decision_accuracy_baseline_on_paired_jobs']:.1%} | "
            f"{metric['decision_accuracy_fastembed_on_paired_jobs']:.1%} | "
            f"{metric['decision_accuracy_delta_on_paired_jobs']:+.1%} | {metric['recall_improved']} | "
            f"{metric['recall_decreased']} | {metric['recall_improved_but_decision_correctness_unchanged']} | "
            f"{metric['retrieval_decreased_and_decision_correctness_decreased']} |"
        )
    rows.extend([
        "",
        "All-job decision accuracy is also reported above; paired accuracy here is restricted to rows with relevant evidence so that each decision can be aligned with retrieval metrics.",
    ])
    rows.extend([
        "",
        "## Does better retrieval improve decisions?",
        "",
        "Each decision comparison below is paired with retrieval on the same persona/job and matching variant; rows have at least one gold evidence item "
        "(retrieval metrics are undefined for no-relevance cases). All-job decision metrics, including no-relevance cases, are reported separately above.",
        "",
        "Examples of retrieval/decision divergence (descriptive association, not proof of causation):",
        "",
        "| Variant | Pattern | Persona | Job ID | Δ recall@5 | Baseline action | FastEmbed action | Correctness baseline → FastEmbed |",
        "|---|---|---|---|---:|---|---|---|",
    ])
    for variant, summary in result["paired_decision_analysis"]["by_variant"].items():
        rows.append(
            f"| `{variant}` | Recall improved / correctness unchanged | — | — | — | — | — | "
            f"{summary['recall_improved_but_decision_correctness_unchanged']} cases "
            f"({summary['recall_improved_but_decision_still_incorrect']} remained incorrect) |"
        )
        for case in summary["examples_recall_improved_no_correctness_gain"][:3]:
            rows.append(
                f"| `{variant}` | Recall improved / correctness unchanged | {case['persona']} | "
                f"`{case['job_id']}` | {case['recall_delta']:+.4f} | {case['baseline_action']} | "
                f"{case['fastembed_action']} | {case['baseline_correct']} → {case['fastembed_correct']} |"
            )
        for pattern, key in (
            ("Recall decreased / correctness harmed", "examples_retrieval_decrease_with_decision_harm"),
            ("Recall decreased / correctness improved", "examples_retrieval_decrease_but_decision_improved"),
        ):
            for case in summary[key][:3]:
                rows.append(
                    f"| `{variant}` | {pattern} | {case['persona']} | `{case['job_id']}` | "
                    f"{case['recall_delta']:+.4f} | {case['baseline_action']} | {case['fastembed_action']} | "
                    f"{case['baseline_correct']} → {case['fastembed_correct']} |"
                )
        rows.append(
            f"| `{variant}` | **Paired summary** | **{summary['n_paired_jobs']} rows** | — | — | — | — | "
            f"Recall improved {summary['recall_improved']}; unchanged {summary['recall_unchanged']}; decreased "
            f"{summary['recall_decreased']}. Decision accuracy: "
            f"{summary['decision_accuracy_baseline_on_paired_jobs']:.1%} → "
            f"{summary['decision_accuracy_fastembed_on_paired_jobs']:.1%}; actions changed "
            f"{summary['decision_action_changed']}; correctness improved "
            f"{summary['decision_correctness_improved']} / decreased {summary['decision_correctness_decreased']}. |"
        )
    rows.extend([
        "",
        "This paired comparison is descriptive. Better-ranked evidence may not change the rule-based fit threshold, risk decision, "
        "or generated proposal; the heuristic writer and formula-derived gold are authored together. Decision changes cannot be attributed "
        "to retrieval alone, and no significance test is claimed.",
        "",
        "## Limitations and instructor-data handoff",
        "",
        "- All dev jobs in this run are synthetic generated jobs with synthetic rule-derived gold; all freelancer portfolios are synthetic. "
        "The source Kaggle postings have no bid/skip or evidence relevance labels. No instructor development dataset was available.",
        "- The claim verifier is lexical and the writer is a deterministic test double; claim support categories are not human judgments. "
        "The generated writer's claims were all labelled supported in this run; that is not evidence that claims are factually true in practice.",
        "- There is no model-generated token usage or inference API cost in this experiment. FastEmbed inference is local; local CPU time is captured in retrieval/index latency.",
        "- The synthetic corpus is small. This experiment evaluates a local dense NumPy index, not a production vector database or live marketplace.",
        "- The hashing baseline and FastEmbed condition use the same portfolio items, filters, top-k, RAG variant, dev jobs, decision graph, and heuristic writer.",
        "- To evaluate instructor data later, provide a corpus with `jobs.json`, `portfolio_items.json`, `freelancers.json`, and "
        "`DATA_MANIFEST.json`, plus `dev_<persona>.json` files with `job_id`, `gold_action`, and `gold_evidence`; then run "
        "`python -m evals.rd_b.run_real_embedder --data-dir <corpus> --dev-dir <dev-dir>`. Use the source's actual labels and provenance; "
        "do not relabel synthetic data as instructor ground truth.",
        "- Full per-job rankings, retrieved IDs, decisions, and claim verdicts are in `evals/rd_b/results/`; run "
        "`python -m evals.rd_b.analyze_retrieval` to rebuild this report and chart. No real marketplace performance is claimed.",
        "",
    ])
    return "\n".join(rows)


def analyze() -> dict[str, Any]:
    result = json.loads(AGGREGATE_RESULTS.read_text(encoding="utf-8"))
    retrieval_rows, decision_rows = _read_jsonl(RETRIEVAL_RESULTS), _read_jsonl(DECISION_RESULTS)
    variants = result["configuration"]["retrieval_variants"]
    retrieval: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in EMBEDDERS}
    for embedder in EMBEDDERS:
        for variant in variants:
            all_variant_rows = [row for row in retrieval_rows
                                if row["embedder"] == embedder and row["variant"] == variant]
            retrieval[embedder][variant] = _retrieval_summary(all_variant_rows)
            retrieval[embedder][variant]["by_persona"] = {
                persona: _retrieval_summary([row for row in all_variant_rows if row["persona"] == persona])
                for persona in result["dataset"]["dev_jobs_per_persona"]
            }
    decisions: dict[str, dict[str, Any]] = {name: {} for name in EMBEDDERS}
    for embedder in EMBEDDERS:
        for variant in result["configuration"]["decision_variants"]:
            rows = [row for row in decision_rows
                    if row["embedder"] == embedder and row["variant"] == variant]
            decisions[embedder][variant] = {
                "overall": _decision_summary(rows),
                "by_persona": {
                    persona: _decision_summary([row for row in rows if row["persona"] == persona])
                    for persona in result["dataset"]["dev_jobs_per_persona"]
                },
            }
    result["retrieval"] = retrieval
    result["decisions"] = decisions
    paired = _paired_analysis(retrieval_rows, decision_rows)
    result["paired_decision_analysis"] = paired
    result["paired_v1_job_analysis"] = paired["by_variant"]["v1_decomposed"]
    result["statistical_significance_claimed"] = False
    AGGREGATE_RESULTS.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    CHART_PATH.write_text(_svg(retrieval, decisions), encoding="utf-8")
    REPORT_PATH.write_text(_report(result), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
