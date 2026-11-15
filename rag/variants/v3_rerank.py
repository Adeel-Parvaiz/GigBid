"""V3: score a wider candidate pool with the configured cross-encoder backend."""
import asyncio


def build_search(base, reranker, pool=20):
    async def search(query, k, filters=None):
        candidates = await base(query, max(k, pool), filters)
        if not candidates:
            return []
        texts = [f"{c['title']}. {c['summary']} {' '.join(c['skills'])}" for c in candidates]
        scores = await asyncio.to_thread(reranker.score, query, texts)
        ordered = sorted(zip(scores, range(len(candidates)), strict=True), key=lambda x: -x[0])
        return [{**candidates[i], 'score': score} for score, i in ordered[:k]]
    return search
