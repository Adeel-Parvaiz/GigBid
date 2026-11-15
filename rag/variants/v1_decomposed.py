"""V1: one retrieval per extracted requirement, merged with reciprocal rank fusion."""
from __future__ import annotations

import asyncio

from rag.variants.v0_naive import RetrievalQuery, SearchFn
from rag.variants.v0_naive import retrieve as _whole_post


async def retrieve(query: RetrievalQuery, search: SearchFn, k: int = 5, per_req: int = 3, rrf_k: int = 60):
    if not query.requirements:
        return await _whole_post(query, search, k)
    results = await asyncio.gather(*(search(r, per_req, query.filters) for r in query.requirements))
    fused: dict[str, float] = {}
    by_id: dict[str, dict] = {}
    for hits in results:
        for rank, hit in enumerate(hits):
            fused[hit["evidence_id"]] = fused.get(hit["evidence_id"], 0.0) + 1.0 / (rrf_k + rank + 1)
            by_id.setdefault(hit["evidence_id"], hit)
    ranked = sorted(fused, key=fused.get, reverse=True)[:k]
    return [{**by_id[i], "score": fused[i]} for i in ranked]
