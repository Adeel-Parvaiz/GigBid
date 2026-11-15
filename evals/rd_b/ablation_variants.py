"""One-factor retrieval ablations for the preregistered R&D B experiment."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from rag.index.bm25 import BM25Index
from rag.index.vector import DenseIndex
from rag.rerank import Reranker
from rag.retriever import dense_search
from rag.variants.v0_naive import RetrievalQuery, SearchFn
from rag.variants.v0_naive import retrieve as whole_query
from rag.variants.v1_decomposed import retrieve as decomposed_query
from rag.variants.v2_hybrid import build_search as build_hybrid_search
from rag.variants.v3_rerank import build_search as build_reranked_search

RetrieveFn = Callable[[RetrievalQuery, int], Awaitable[list[dict[str, Any]]]]


@dataclass(frozen=True)
class AblationCondition:
    name: str
    decomposition: bool
    hybrid: bool
    reranking: bool


CONDITIONS = (
    AblationCondition("v0_naive", False, False, False),
    AblationCondition("v1_v2_v3", True, True, True),
    AblationCondition("no_decomposition", False, True, True),
    AblationCondition("no_hybrid", True, False, True),
    AblationCondition("no_reranking", True, True, False),
)


def build_condition_retrievers(
    dense_index: DenseIndex,
    bm25: BM25Index,
    reranker: Reranker,
) -> dict[str, RetrieveFn]:
    dense = dense_search(dense_index)
    hybrid = build_hybrid_search(dense_index, bm25)
    retrievers: dict[str, RetrieveFn] = {}
    for condition in CONDITIONS:
        search = hybrid if condition.hybrid else dense
        if condition.reranking:
            search = build_reranked_search(search, reranker)
        query = decomposed_query if condition.decomposition else whole_query

        async def retrieve(
            request: RetrievalQuery,
            k: int = 10,
            *,
            search_fn: SearchFn = search,
            query_fn: Callable[..., Awaitable[list[dict[str, Any]]]] = query,
        ) -> list[dict[str, Any]]:
            return await query_fn(request, search_fn, k=k)

        retrievers[condition.name] = retrieve
    return retrievers
