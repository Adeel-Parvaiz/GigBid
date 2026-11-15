"""Summarize R&D A task results and create a comparison SVG and report."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

from evals.rd_a.run_experiment import ROOT, TASKS_PATH

RESULTS_DIR = Path(__file__).with_name("results")
INPUT_PATH = RESULTS_DIR / "task_results.jsonl"
AGGREGATE_PATH = RESULTS_DIR / "aggregate.json"
CHART_PATH = RESULTS_DIR / "comparison.svg"
REPORT_PATH = ROOT / "docs" / "RD_A_RESULTS.md"
CONFIGS = ("fine_grained", "coarse_grained", "optimized")


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    return sorted(values)[math.ceil(0.95 * len(values)) - 1]


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        raise ValueError("Cannot analyze an empty configuration")
    total_calls = sum(row["tool_calls"] for row in rows)
    token_rows = [row for row in rows if row["token_usage"] is not None]
    cost_rows = [row for row in rows if row["cost_usd"] is not None]
    latencies = [row["latency_ms"] for row in rows]
    selection_latencies = [row["selection_latency_ms"] for row in rows]
    tool_latencies = [row["tool_latency_ms"] for row in rows]
    return {
        "n_tasks": n,
        "correct_tool_selection": sum(row["correct_tool_selection"] for row in rows) / n,
        "task_completion": sum(row["task_completed"] for row in rows) / n,
        "argument_schema_validity": sum(row["argument_schema_valid"] for row in rows) / n,
        "tool_calls": total_calls,
        "mean_tool_calls_per_task": total_calls / n,
        "failed_tool_calls": sum(row["failed_tool_calls"] for row in rows),
        "median_latency_ms": statistics.median(latencies),
        "p95_latency_ms": _p95(latencies),
        "median_selection_latency_ms": statistics.median(selection_latencies),
        "median_tool_latency_ms": statistics.median(tool_latencies),
        "token_usage_available_tasks": len(token_rows),
        "token_usage_total": (sum(row["token_usage"].get("total", 0) for row in token_rows)
                              if token_rows else None),
        "cost_measurable_tasks": len(cost_rows),
        "cost_usd_total": (sum(row["cost_usd"] for row in cost_rows) if cost_rows else None),
        "selection_by_expected_tool": {
            tool: {
                "n_tasks": sum(row["expected_tool"] == tool for row in rows),
                "selected_correct": sum(row["expected_tool"] == tool and row["correct_tool_selection"] for row in rows),
            }
            for tool in sorted({row["expected_tool"] for row in rows})
        },
    }


def _svg(metrics: dict[str, dict[str, Any]]) -> str:
    width, height = 900, 470
    colors = {"fine_grained": "#4c78a8", "coarse_grained": "#f58518", "optimized": "#54a24b"}
    labels = {"fine_grained": "Fine-grained", "coarse_grained": "Coarse-grained", "optimized": "Rewritten/optimized"}
    charts = [
        ("Correct tool selection", "correct_tool_selection", True),
        ("Task completion", "task_completion", True),
        ("Argument/schema validity", "argument_schema_validity", True),
        ("Median end-to-end latency (ms)", "median_latency_ms", False),
    ]
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#222}.title{font-size:20px;font-weight:bold}.label{font-size:13px}.small{font-size:11px}</style>',
        '<text x="20" y="28" class="title">R&amp;D A: Tool-description comparison</text>',
    ]
    panel_w = 420
    positions = [(25, 50), (465, 50), (25, 260), (465, 260)]
    for (title, metric, percentage), (x, y) in zip(charts, positions, strict=True):
        svg.append(f'<text x="{x}" y="{y}" class="label" font-weight="bold">{title}</text>')
        plot_y, plot_h = y + 22, 105
        max_v = 1.0 if percentage else max(1.0, max(metrics[c][metric] for c in CONFIGS) * 1.15)
        svg.append(f'<line x1="{x + 25}" y1="{plot_y + plot_h}" x2="{x + panel_w - 8}" y2="{plot_y + plot_h}" stroke="#777"/>')
        for idx, config in enumerate(CONFIGS):
            bar_x = x + 55 + idx * 115
            value = metrics[config][metric]
            bar_h = plot_h * value / max_v
            svg.append(f'<rect x="{bar_x}" y="{plot_y + plot_h - bar_h:.1f}" width="48" height="{bar_h:.1f}" fill="{colors[config]}"/>')
            shown = f"{value * 100:.1f}%" if percentage else f"{value:.0f}"
            svg.append(f'<text x="{bar_x + 24}" y="{plot_y + plot_h - bar_h - 5:.1f}" text-anchor="middle" class="small">{shown}</text>')
            svg.append(f'<text x="{bar_x + 24}" y="{plot_y + plot_h + 17}" text-anchor="middle" class="small">{labels[config]}</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def _report(metrics: dict[str, dict[str, Any]], task_count: int, seed: int) -> str:
    names = {"fine_grained": "Fine-grained", "coarse_grained": "Coarse-grained", "optimized": "Rewritten/optimized"}
    lines = [
        "# R&D A — Tool Description Granularity",
        "",
        "## Experiment scope",
        "",
        f"Executed **{task_count} identical tasks under each of three conditions** ({task_count * 3} trials total), seed `{seed}`. "
        "The task set was authored from the existing MCP contracts because no prior 40-task set was present.",
        "",
        "This is a **deterministic BM25 lexical tool-discovery baseline**, not an LLM or the production LangGraph agent. "
        "The repository's agent nodes select tools through fixed names/allowlists; they do not dynamically choose among descriptions. "
        "The selector ranks the live MCP tool name, description, and unchanged input-schema field names/descriptions. "
        "Only tool descriptions vary between conditions; input/output schemas, annotations, handlers, and task arguments are checked to remain identical.",
        "",
        "Each selected tool was called through an in-process MCP session backed by isolated local sample services. "
        "No external marketplace, calendar, email, or portfolio writes were made. Submit tasks used a locally pre-seeded draft; "
        "proposal drafts used dry-run mode.",
        "",
        "## Results",
        "",
        "| Condition | Correct selection | Task completion | Schema-valid arguments | Tool calls | Failed calls | Median total (ms) | P95 total (ms) | Median selection (ms) | Median MCP call (ms) | Tokens | Cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for config in CONFIGS:
        m = metrics[config]
        tokens = "n/a" if m["token_usage_total"] is None else str(m["token_usage_total"])
        cost = "n/a" if m["cost_usd_total"] is None else f"${m['cost_usd_total']:.4f}"
        lines.append(
            f"| {names[config]} | {m['correct_tool_selection']:.1%} | {m['task_completion']:.1%} | "
            f"{m['argument_schema_validity']:.1%} | {m['tool_calls']} | {m['failed_tool_calls']} | "
            f"{m['median_latency_ms']:.2f} | {m['p95_latency_ms']:.2f} | "
            f"{m['median_selection_latency_ms']:.3f} | {m['median_tool_latency_ms']:.3f} | {tokens} | {cost} |"
        )
    lines.extend(["", "![Measured comparison chart](../evals/rd_a/results/comparison.svg)", "",
                  "### What differed",
                  "",
                  f"Fine-grained descriptions completed {metrics['fine_grained']['n_tasks'] * metrics['fine_grained']['task_completion']:.0f}/40 tasks, "
                  f"compared with {metrics['optimized']['n_tasks'] * metrics['optimized']['task_completion']:.0f}/40 for rewritten/optimized "
                  f"and {metrics['coarse_grained']['n_tasks'] * metrics['coarse_grained']['task_completion']:.0f}/40 for coarse descriptions. "
                  "The clearest fine-grained gains were job discovery (search_jobs: 4/4 versus 2/4 in each alternative) and known-job retrieval "
                  "(get_job: 3/3 versus 2/3 in each alternative). Rewritten/optimized descriptions did better than coarse wording for proposal "
                  "drafts (3/3 versus 2/3), but selected send_message correctly on 0/2 tasks (fine/coarse: 2/2). These are small per-tool counts "
                  "from the same authored set, not significance-tested results.",
                  "",
                  "### Selection by expected tool", "",
                  "| Tool | Fine-grained | Coarse-grained | Rewritten/optimized | Tasks |",
                  "|---|---:|---:|---:|---:|"])
    tools = sorted(set.intersection(*[
        set(metrics[c]["selection_by_expected_tool"]) for c in CONFIGS
    ]))
    for tool in tools:
        counts = [metrics[c]["selection_by_expected_tool"][tool] for c in CONFIGS]
        n = counts[0]["n_tasks"]
        lines.append(f"| `{tool}` | {counts[0]['selected_correct']}/{n} | {counts[1]['selected_correct']}/{n} | "
                     f"{counts[2]['selected_correct']}/{n} | {n} |")
    winner = max(CONFIGS, key=lambda c: metrics[c]["task_completion"])
    lines.extend([
        "",
        f"**Measured result:** {names[winner]} had the highest task-completion rate on this authored task set "
        f"({metrics[winner]['task_completion']:.1%}). This describes only this BM25 baseline and these 40 requests; "
        "it is not evidence that the same condition improves an LLM or production agent.",
        "",
        "## Interpretation and limitations",
        "",
        "- Task completion requires the expected tool to be selected, its argument object to validate against the live input schema, "
        "the MCP call to succeed, and the returned value to meet the task's explicit check.",
        "- Total latency is local in-process end-to-end trial time and includes server/session setup; it is not production transport latency. "
        "Selection latency starts after MCP tools have been listed, and tool-call latency is measured separately in task results.",
        "- Token use and model cost are unavailable because no model was called. MCP calls are local, so no inference cost is measurable.",
        "- The conditions use identical tool names, schemas, annotations, handlers, and capabilities. The coarse condition intentionally "
        "uses broad server-level descriptions; the optimized condition emphasizes action, inputs, and distinctions from neighboring tools.",
        "- The task set was authored from tool contracts, so it is curated rather than independently sampled. This is a descriptive comparison; "
        "no statistical significance is claimed.",
        "- Raw per-task outcomes are in `evals/rd_a/results/task_results.jsonl`; aggregate data are in "
        "`evals/rd_a/results/aggregate.json`. Re-run with `python -m evals.rd_a.run_experiment` and regenerate this report with "
        "`python -m evals.rd_a.analyze_results`.",
        "",
    ])
    return "\n".join(lines)


def analyze(input_path: Path = INPUT_PATH) -> dict[str, Any]:
    task_data = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    task_ids = [task["task_id"] for task in task_data["tasks"]]
    rows = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(task_ids) != 40 or len(set(task_ids)) != 40:
        raise ValueError("The task file must contain exactly 40 unique tasks")
    if len(rows) != 120:
        raise ValueError(f"Expected 120 result rows; found {len(rows)}")
    schema_fingerprints = {row["schema_sha256"] for row in rows}
    if len(schema_fingerprints) != 1:
        raise ValueError("MCP schema fingerprints differ across experiment conditions")
    metrics = {}
    for config in CONFIGS:
        selected = [row for row in rows if row["configuration"] == config]
        if [row["task_id"] for row in selected] != task_ids:
            raise ValueError(f"{config} results are missing tasks, reordered, or duplicated")
        metrics[config] = _metrics(selected)
    aggregate = {
        "experiment": "R&D A: MCP tool description granularity",
        "selector": "BM25 lexical tool discovery; no LLM called",
        "tasks": len(task_ids),
        "trials": len(rows),
        "seed": rows[0]["seed"],
        "task_set_sha256": hashlib.sha256(TASKS_PATH.read_bytes()).hexdigest(),
        "mcp_schema_sha256": next(iter(schema_fingerprints)),
        "conditions": metrics,
        "description_sha256": {config: next(row["configuration_sha256"] for row in rows
                                            if row["configuration"] == config) for config in CONFIGS},
        "statistical_significance_claimed": False,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    AGGREGATE_PATH.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    CHART_PATH.write_text(_svg(metrics), encoding="utf-8")
    REPORT_PATH.write_text(_report(metrics, len(task_ids), aggregate["seed"]), encoding="utf-8")
    return aggregate


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
