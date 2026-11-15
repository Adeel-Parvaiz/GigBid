"""Simulated reply/hire rate per RAG variant on the local simulator. python -m evals.runners.gigsim_outcomes --persona ai-ml-engineer

Harness only: a scripted 'human' approves every unblocked draft so outcomes can be measured. The product itself never auto-sends.
Outcomes come from evals' LocalSimAdapter (rule-based clients): see its docstring for what the numbers do and do not mean."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.runtime import build_deps, load_sample_profile
from evals.common import ROOT, write_result
from evals.metrics import mean, wilson
from mcp_servers.marketplace.adapters.localsim import LocalSimAdapter
from rag.retriever import VARIANTS


async def run_variant(variant: str, persona: str, dev: list[dict], data_dir: Path, n: int, llm=None, seed: int = 7) -> dict:
    cfg = load_config(overrides={"rag": {"variant": variant}})
    port = LocalSimAdapter(data_dir, seed=seed)
    deps = build_deps(cfg, port=port, llm=llm, data_dir=data_dir)
    profile = load_sample_profile(persona, data_dir)
    g = build_bid_graph(deps, InMemorySaver())
    jobs = [d["job_id"] for d in dev if d["gold_action"] == "bid"][:n]
    bid = blocked = 0
    unsupported, fit = [], []
    for jid in jobs:
        cfgd = {"configurable": {"thread_id": f"{variant}-{jid}"}}
        out = await g.ainvoke({"job_id": jid, "profile": profile}, cfgd)
        fit.append(out["fit_report"].score)
        if out["decision"].action != "bid":
            continue
        bid += 1
        unsupported.append(out.get("verification_stats", {}).get("unsupported_before", 0))
        snap = await g.aget_state(cfgd)
        pend = next((i.value for t in snap.tasks for i in t.interrupts), None)
        if pend is None or "approve" not in pend["allowed_actions"]:
            blocked += 1
            continue
        await g.ainvoke(Command(resume={"action": "approve"}), cfgd)
    outs = [port.outcome_for(k) for k in port.submissions]
    sub = len(outs)
    rep, hired = sum(o["replied"] for o in outs), sum(o["hired"] for o in outs)
    return {"gold_bid_jobs_tried": len(jobs), "recommended_bid": bid, "blocked": blocked, "submitted": sub,
            "reply_rate": rep / sub if sub else None, "reply_rate_95ci": wilson(rep, sub),
            "hire_rate": hired / sub if sub else None, "hire_rate_95ci": wilson(hired, sub),
            "mean_p_reply": mean([o["p_reply"] for o in outs]), "mean_fit": mean(fit), "mean_unsupported_before": mean(unsupported)}


async def run(persona: str, data_dir: Path, dev_path: Path, n: int, variants: list[str] | None = None, llm=None) -> dict:
    dev = json.loads(dev_path.read_text())["jobs"]
    return {v: await run_variant(v, persona, dev, data_dir, n, llm) for v in (variants or sorted(VARIANTS))}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True)
    ap.add_argument("--data-dir", default=str(ROOT / "data/processed"))
    ap.add_argument("--dev", help="default: evals/datasets/dev_<persona>.json")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--variants")
    a = ap.parse_args()
    res = asyncio.run(run(a.persona, Path(a.data_dir), Path(a.dev or ROOT / f"evals/datasets/dev_{a.persona}.json"), a.n,
                          a.variants.split(",") if a.variants else None))
    print(write_result(f"outcomes_{a.persona}", {"persona": a.persona, "variants": res,
        "caveat": "rates come from a rule-based simulated client; compare variants, do not quote as real reply rates; intervals are wide at this n"},
        corpus="synthetic+local-sim", llm="heuristic-double"))
