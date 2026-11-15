"""Bid-or-skip F1, scam P/R, price-in-band, claim verification before/after, latency. python -m evals.runners.decision_eval"""
from __future__ import annotations

import asyncio
import time

from langgraph.checkpoint.memory import InMemorySaver

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.handoffs import Claim, ProposalDraft
from agent.llm import HeuristicLLM
from agent.runtime import build_deps, load_sample_profile
from evals.common import load_dev, write_result
from evals.metrics import mean, percentile, prf


class FabricatingWriter(HeuristicLLM):
    """Synthetic perturbation: every draft gets one invented claim. Measures that the verifier catches it."""
    def _writer(self, i):
        d = super()._writer(i)
        d.claims.insert(1, Claim(text="I led a team of 12 engineers at Google for 8 years.", evidence_ids=[], kind="claim"))
        return d


async def run(cfg_over: dict | None = None, llm=None, dev=None, persona: str | None = None, data_dir=None) -> dict:
    cfg, profile, dev = load_config(overrides=cfg_over), load_sample_profile(persona, data_dir), dev or load_dev()
    deps = build_deps(cfg, llm=llm, data_dir=data_dir)
    g, rows = build_bid_graph(deps, InMemorySaver()), []
    for d in dev:
        t0 = time.perf_counter()
        out = await g.ainvoke({"job_id": d["job_id"], "profile": profile}, {"configurable": {"thread_id": d["job_id"]}})
        ms = (time.perf_counter() - t0) * 1000
        flags = set(out["risk_report"].flags)
        stats = out.get("verification_stats", {})
        q = out.get("price_quote")
        rows.append({"job_id": d["job_id"], "action": out["decision"].action, "gold": d["gold_action"],
                     "scam_pred": bool(flags & {"unpaid_work", "off_platform_contact", "prompt_injection"}),
                     "scam_gold": d["scam"] or d["injection"], "template_set": d.get("template_set"), "ms": ms,
                     "price_in_band": (d["price_band"][0] <= q.amount <= d["price_band"][1]) if q and d["price_band"] else None,
                     "unsupported_before": stats.get("unsupported_before"), "unsupported_after": stats.get("unsupported_after"),
                     "claims_total": stats.get("claims_total")})
    bid = prf([r["action"] == "bid" for r in rows], [r["gold"] == "bid" for r in rows])
    scam = prf([r["scam_pred"] for r in rows], [r["scam_gold"] for r in rows])
    drafted = [r for r in rows if r["claims_total"]]
    pb = [r["price_in_band"] for r in rows if r["price_in_band"] is not None]
    by_set = {t: (lambda xs: {"n": len(xs), "recall": sum(r["scam_pred"] for r in xs) / len(xs)})([r for r in rows if r["template_set"] == t])
              for t in ("seeded", "heldout") if any(r["template_set"] == t for r in rows)}
    return {"n_jobs": len(rows), "bid_or_skip": bid, "scam_or_injection_detection": scam, "scam_or_injection_recall_by_template_set": by_set,
            "price_in_band_rate": sum(pb) / len(pb) if pb else None,
            "unsupported_claims_per_proposal_before": mean([r["unsupported_before"] for r in drafted]),
            "unsupported_claims_per_proposal_after": mean([r["unsupported_after"] for r in drafted]),
            "latency_ms_p50": percentile([r["ms"] for r in rows], .5), "latency_ms_p95": percentile([r["ms"] for r in rows], .95),
            "per_job": rows}


if __name__ == "__main__":
    import argparse
    import json as _json
    from pathlib import Path as _P
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona")
    ap.add_argument("--dev")
    ap.add_argument("--data-dir")
    a = ap.parse_args()
    if a.persona:
        dev = _json.loads(_P(a.dev or f"evals/datasets/dev_{a.persona}.json").read_text())["jobs"]
        r = asyncio.run(run(dev=dev, persona=a.persona, data_dir=a.data_dir))
        print(write_result(f"decision_eval_{a.persona}", {"base": r}, corpus="synthetic-dev-200", llm="heuristic-double"))
        raise SystemExit
    base = asyncio.run(run())
    fab = asyncio.run(run(llm=FabricatingWriter()))
    fab_off = asyncio.run(run({"defences": {"verify_claims": False}}, llm=FabricatingWriter()))
    print(write_result("decision_eval", {"base": base,
        "fabricating_writer_verifier_on": {k: fab[k] for k in ("unsupported_claims_per_proposal_before", "unsupported_claims_per_proposal_after")},
        "fabricating_writer_verifier_off": {k: fab_off[k] for k in ("unsupported_claims_per_proposal_before", "unsupported_claims_per_proposal_after")}}))
_ = ProposalDraft
