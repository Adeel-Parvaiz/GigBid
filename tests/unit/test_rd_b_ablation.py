import asyncio

from evals.rd_b.ablation_variants import CONDITIONS, build_condition_retrievers
from rag.variants.v0_naive import RetrievalQuery


class FakeBM25:
    def __init__(self, calls):
        self.calls = calls

    def search(self, query, k, filters=None):
        self.calls.append(("bm25", query))
        return [{"evidence_id": f"shared-{query}", "title": query, "summary": query, "skills": []}]


class FakeReranker:
    def score(self, query, docs):
        return [1.0] * len(docs)


class FakeDenseIndex:
    def __init__(self, calls):
        self.calls = calls

    def search(self, query, k, filters=None):
        self.calls.append(("dense", query))
        return [{"evidence_id": f"shared-{query}", "title": query, "summary": query, "skills": []}]


def test_ablation_conditions_remove_exactly_one_component():
    conditions = {condition.name: condition for condition in CONDITIONS}
    full = conditions["v1_v2_v3"]
    assert (full.decomposition, full.hybrid, full.reranking) == (True, True, True)
    assert (conditions["no_decomposition"].decomposition,
            conditions["no_decomposition"].hybrid,
            conditions["no_decomposition"].reranking) == (False, True, True)
    assert (conditions["no_hybrid"].decomposition,
            conditions["no_hybrid"].hybrid,
            conditions["no_hybrid"].reranking) == (True, False, True)
    assert (conditions["no_reranking"].decomposition,
            conditions["no_reranking"].hybrid,
            conditions["no_reranking"].reranking) == (True, True, False)


def test_each_retriever_composes_only_its_declared_components():
    async def verify():
        calls = []
        query = RetrievalQuery("whole job", ["skill alpha", "skill beta"], {"freelancer_id": "alice"})
        retrievers = build_condition_retrievers(FakeDenseIndex(calls), FakeBM25(calls), FakeReranker())
        await retrievers["no_decomposition"](query)
        assert calls == [("dense", "whole job"), ("bm25", "whole job")]

        calls.clear()
        await retrievers["no_hybrid"](query)
        assert calls == [("dense", "skill alpha"), ("dense", "skill beta")]

        calls.clear()
        await retrievers["no_reranking"](query)
        assert calls == [
            ("dense", "skill alpha"), ("bm25", "skill alpha"),
            ("dense", "skill beta"), ("bm25", "skill beta"),
        ]

    asyncio.run(verify())
