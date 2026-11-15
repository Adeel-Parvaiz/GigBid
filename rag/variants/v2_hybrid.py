"""V2: BM25 plus cosine rankings with reciprocal rank fusion."""
def rrf(lists, k, rrf_k=60):
    scores, items = {}, {}
    for hits in lists:
        for rank, hit in enumerate(hits, 1):
            eid = hit['evidence_id']
            scores[eid] = scores.get(eid, 0) + 1 / (rrf_k + rank)
            items.setdefault(eid, hit)
    return [{**items[eid], 'score': scores[eid]} for eid in sorted(scores, key=scores.get, reverse=True)[:k]]


def build_search(dense, bm25, pool=20):
    async def search(query, k, filters=None):
        return rrf([dense.search(query, max(k, pool), filters), bm25.search(query, max(k, pool), filters)], k)
    return search
