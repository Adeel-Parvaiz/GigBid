"""Retrieval metrics per variant: Recall@5, MRR, nDCG@10 against gold evidence. python -m evals.runners.rag_eval"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agent.config import load_config
from agent.nodes.fit_matcher import requirements_of
from agent.runtime import DATA, load_sample_profile
from evals.common import load_dev, write_result
from evals.metrics import mean, mrr, ndcg_at_k, recall_at_k
from mcp_servers.marketplace.adapters.sample import SampleAdapter
from rag.retriever import VARIANTS, RetrievalQuery, build_retriever


async def run(variants=None, dev=None, persona: str | None = None, data_dir: str | Path | None = None) -> dict:
    directory = Path(data_dir) if data_dir else DATA
    cfg, items = load_config(), json.loads((directory / "portfolio_items.json").read_text())
    fid = load_sample_profile(persona, directory)["freelancer_id"]
    port, dev = SampleAdapter(directory), dev or load_dev()
    out = {}
    for v in variants or sorted(VARIANTS):
        r = build_retriever({**cfg, "rag": {**cfg["rag"], "variant": v}}, items)
        rows = []
        for d in (x for x in dev if x["gold_evidence"]):
            job = await port.get_job(d["job_id"])
            q = RetrievalQuery(f"{job['title']}. {job['description']}", requirements_of(job), {"freelancer_id": fid})
            ranked = [h["evidence_id"] for h in await r.retrieve(q, 10)]
            g = set(d["gold_evidence"])
            rows.append({"job_id": d["job_id"], "recall@5": recall_at_k(ranked, g, 5), "mrr": mrr(ranked, g), "ndcg@10": ndcg_at_k(ranked, g, 10)})
        out[v] = {"n_jobs": len(rows), **{m: mean([x[m] for x in rows]) for m in ("recall@5", "mrr", "ndcg@10")}, "per_job": rows}
    return out


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
        res = asyncio.run(run(dev=dev, persona=a.persona, data_dir=a.data_dir))
        print(write_result(f"rag_eval_{a.persona}", {"variants": res}, corpus="synthetic-dev-200", llm="n/a (retrieval only)"))
        raise SystemExit
    res = asyncio.run(run())
    print(write_result("rag_eval", {"variants": res, "corpus_items": 4,
                                    "caveat": "4 items and k>=4 means every variant retrieves everything; differences are meaningless here"}))
