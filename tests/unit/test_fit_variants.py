from rag.retriever import RetrievalQuery


async def test_both_variants_run_and_filter_by_freelancer(make_deps):
    for variant in ("v0_naive", "v1_decomposed"):
        deps = make_deps({"rag": {"variant": variant}})
        q = RetrievalQuery("fraud classifier dashboard", ["scikit-learn", "dashboarding"],
                           {"freelancer_id": "sample-ai-engineer"})
        hits = await deps.retriever.retrieve(q, 3)
        assert hits and all(h["freelancer_id"] == "sample-ai-engineer" for h in hits)
    q.filters = {"freelancer_id": "someone-else"}
    assert await deps.retriever.retrieve(q, 3) == []
