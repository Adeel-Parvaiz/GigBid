"""Paired real-LLM comparison on the versioned synthetic dev set; never submits drafts."""
from __future__ import annotations

import argparse
import asyncio
import contextvars
import hashlib
import json
import math
import platform
import random
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from langgraph.checkpoint.memory import InMemorySaver

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.llm import OpenAICompatLLM
from agent.runtime import build_deps, load_sample_profile
from evals.metrics import mean, percentile, prf

NODE = contextvars.ContextVar("comparison_node", default="unknown")
PERSONAS = ("ai-ml-engineer", "fullstack-dev", "data-analyst")


class MeasuredLLM(OpenAICompatLLM):
    def __init__(self, cfg, client=None):
        self.calls = []
        super().__init__(cfg, client or httpx.AsyncClient(timeout=180, event_hooks={"request": [self.start], "response": [self.record]}))

    async def start(self, request):
        request.extensions["comparison_started"] = time.perf_counter()

    async def record(self, response):
        await response.aread()
        body = json.loads(response.request.content)
        payload = response.json() if response.is_success else {}
        usage = payload.get("usage", {})
        self.calls.append({"node": NODE.get(), "model": body["model"], "http_status": response.status_code,
                           "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                           "output": payload.get("choices", [{}])[0].get("message", {}).get("content"),
                           "seconds": time.perf_counter() - response.request.extensions.get("comparison_started", time.perf_counter())})

    async def structured(self, node, schema, inputs):
        token = NODE.set(node)
        try:
            return await super().structured(node, schema, inputs)
        finally:
            NODE.reset(token)


def finite(value):
    if isinstance(value, dict):
        return {k: finite(v) for k, v in value.items()}
    if isinstance(value, list):
        return [finite(v) for v in value]
    return None if isinstance(value, float) and not math.isfinite(value) else value


def summarize(rows):
    done = [r for r in rows if r["completed"]]
    drafts = [r for r in done if r.get("claims_total")]
    calls = [c for r in rows for c in r["calls"]]
    known = all(c["prompt_tokens"] is not None and c["completion_tokens"] is not None for c in calls)
    output_tokens = sum(c["completion_tokens"] for c in calls) if known else None
    call_seconds = sum(c.get("seconds", 0) for c in calls)
    priced = [r["price_in_band"] for r in done if r.get("price_in_band") is not None]
    return finite({"attempted": len(rows), "completed": len(done), "errors": len(rows) - len(done),
        "completion_rate": len(done) / len(rows) if rows else None,
        "accuracy_including_errors": sum(r["action"] == r["gold"] for r in done) / len(rows) if rows else None,
        "bid_f1_completed": prf([r["action"] == "bid" for r in done], [r["gold"] == "bid" for r in done]),
        "scam_detection_completed": prf([r["scam_pred"] for r in done], [r["scam_gold"] for r in done]),
        "drafts": len(drafts), "unsupported_before_per_draft": mean([r["unsupported_before"] for r in drafts]),
        "priced_jobs": len(priced), "price_in_band_rate": sum(priced) / len(priced) if priced else None,
        "unsupported_after_per_draft": mean([r["unsupported_after"] for r in drafts]),
        "latency_seconds_p50": percentile([r["seconds"] for r in rows], .5),
        "latency_seconds_p95": percentile([r["seconds"] for r in rows], .95),
        "http_calls": len(calls), "usage_complete": known,
        "prompt_tokens": sum(c["prompt_tokens"] for c in calls) if known else None,
        "completion_tokens": output_tokens,
        "completion_tokens_per_http_second": output_tokens / call_seconds if known and call_seconds > 0 else None,
        "tokens_per_job": sum(c["prompt_tokens"] + c["completion_tokens"] for c in calls) / len(rows) if known and rows else None,
        "draft_job_seconds_p95": percentile([r["seconds"] for r in drafts], .95)})


async def run(args):
    root = Path(__file__).resolve().parents[2]
    data, devdir = root / args.data_dir, root / args.dev_dir
    models = args.models
    if len(set(models)) != 2:
        raise ValueError("Provide two different real model tags")
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    excluded = set()
    if args.exclude_from:
        excluded = {(r["persona"], r["job_id"]) for r in json.loads((root / args.exclude_from).read_text())["rows"]}
    meta = {"models": models, "endpoint": args.base_url, "seed": args.seed,
            "dev_per_persona": args.limit, "label_provenance": "synthetic_rule",
            "excluded_pilot_jobs": sorted([list(pair) for pair in excluded]),
            "manifest_sha256": hashlib.sha256((data / "DATA_MANIFEST.json").read_bytes()).hexdigest(),
            "python": platform.python_version(), "hardware": args.hardware,
            "prompt_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root / "agent/prompts").glob("*.md"))},
            "llm_client_sha256": hashlib.sha256((root / "agent/llm.py").read_bytes()).hexdigest(),
            "local_inference": args.local, "api_cost_usd": 0 if args.local else None,
            "cost_note": "Local inference has no API charge; electricity and hardware costs are not measured." if args.local else "Provider billing not configured; cost is unknown.",
            "limitations": ["Synthetic gold; not instructor data or marketplace outcomes.",
                            "Lexical verifier and hashing retrieval held constant.",
                            "Wall-clock latency includes model loading and schema repair.",
                            "No calibrated judge or human panel is claimed."],
            "dev_sha256": {p: hashlib.sha256((devdir / f"dev_{p}.json").read_bytes()).hexdigest() for p in PERSONAS}}
    if args.resume and out.exists():
        result = json.loads(out.read_text())
        if result["meta"] != meta:
            raise ValueError("Resume configuration/data differs from the saved run")
        if result.get("status") == "completed":
            print(f"Already completed: {out}")
            return
    else:
        if out.exists():
            raise ValueError("Output exists; use --resume or choose another --out")
        result = {"meta": meta, "status": "running", "started_at_utc": datetime.now(UTC).isoformat(), "rows": [], "summaries": {}}

    def save():
        result["summaries"] = {m: {"all": summarize([r for r in result["rows"] if r["model"] == m]),
            "personas": {p: summarize([r for r in result["rows"] if r["model"] == m and r["persona"] == p]) for p in PERSONAS}} for m in models}
        temporary = out.with_suffix(".tmp")
        temporary.write_text(json.dumps(finite(result), indent=2), encoding="utf-8")
        temporary.replace(out)

    existing = {(r["model"], r["persona"], r["job_id"]) for r in result["rows"]}
    for model in models:
        cfg = load_config(overrides={"llm": {"backend": "openai_compat", "profile": "open",
            "profiles": {"open": {"base_url": args.base_url, "max_output_tokens": 1536, "nodes": {n: model for n in (
                "analyst", "risk", "writer", "critic", "liaison_intent", "liaison_reply")}}}},
            "portfolio": {"source": "local"}, "marketplace": {"mode": "sample"}, "workspace": {"source": "mcp"},
            "rag": {"embedder": "hashing", "variant": "v1_decomposed"}})
        llm = MeasuredLLM(cfg)
        try:
            for persona in PERSONAS:
                jobs = json.loads((devdir / f"dev_{persona}.json").read_text())["jobs"]
                jobs = [j for j in jobs if (persona, j["job_id"]) not in excluded]
                if len(jobs) < args.limit:
                    raise ValueError("Not enough dev jobs after excluding pilot jobs")
                random.Random(args.seed).shuffle(jobs)
                jobs = jobs[:args.limit]
                profile = load_sample_profile(persona, data)
                deps = build_deps(cfg, llm=llm, data_dir=data)
                graph = build_bid_graph(deps, InMemorySaver())
                for job in jobs:
                    if (model, persona, job["job_id"]) in existing:
                        continue
                    llm.calls.clear()
                    row = {"model": model, "persona": persona, "job_id": job["job_id"],
                           "gold": job["gold_action"], "completed": False}
                    started = time.perf_counter()
                    try:
                        state = await asyncio.wait_for(graph.ainvoke({"job_id": job["job_id"], "profile": profile},
                            {"configurable": {"thread_id": job["job_id"]}}), timeout=args.job_timeout)
                        risk = state["risk_report"]
                        flags = set(risk.flags)
                        stats = state.get("verification_stats", {})
                        if state.get("status") in ("error", "needs_attention"):
                            raise RuntimeError("Graph did not complete its decision/draft path")
                        quote, band = state.get("price_quote"), job.get("price_band")
                        row.update(completed=True, action=state["decision"].action, status=state.get("status"),
                            scam_pred=bool(flags & {"unpaid_work", "off_platform_contact", "prompt_injection"}),
                            scam_gold=job["scam"] or job["injection"], claims_total=stats.get("claims_total", 0),
                            unsupported_before=stats.get("unsupported_before", 0), unsupported_after=stats.get("unsupported_after", 0),
                            price_in_band=(band[0] <= quote.amount <= band[1]) if quote and band else None,
                            compliance=state["compliance_verdict"].model_dump(mode="json") if state.get("compliance_verdict") else None,
                            risk_report=risk.model_dump(mode="json"),
                            job_spec=state["job_spec"].model_dump(mode="json"),
                            fit_report=state["fit_report"].model_dump(mode="json") if state.get("fit_report") else None,
                            draft=state["proposal_draft"].model_dump(mode="json") if state.get("proposal_draft") else None,
                            critique=state["critique"].model_dump(mode="json") if state.get("critique") else None,
                            trace=state.get("trace"))
                    except Exception as error:  # Record failures, never replace a failed model with the heuristic backend.
                        row["error_type"] = type(error).__name__
                        row["error_detail"] = str(error)[:1000]
                        if isinstance(error, httpx.HTTPStatusError):
                            row["http_status"] = error.response.status_code
                    row.update(seconds=round(time.perf_counter() - started, 3), calls=list(llm.calls))
                    result["rows"].append(row)
                    save()
                    print(f"{model} {persona} {job['job_id']} completed={row['completed']} seconds={row['seconds']}", flush=True)
        finally:
            await llm.client.aclose()
    result["status"] = "completed"
    result["finished_at_utc"] = datetime.now(UTC).isoformat()
    save()
    print(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs=2, required=True)
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--data-dir", default="data/processed/kaggle_2024_v1")
    parser.add_argument("--dev-dir", default="evals/datasets/kaggle_2024_v1")
    parser.add_argument("--out", default="evals/results/open_model_comparison.json")
    parser.add_argument("--limit", type=int, default=200, help="Identical seeded dev jobs per persona, maximum 200")
    parser.add_argument("--seed", type=int, default=4016)
    parser.add_argument("--job-timeout", type=int, default=300)
    parser.add_argument("--hardware", required=True)
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--exclude-from", help="Exclude persona/job pairs from a saved pilot before seeded sampling")
    args = parser.parse_args()
    if not 1 <= args.limit <= 200:
        parser.error("--limit must be between 1 and 200")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
