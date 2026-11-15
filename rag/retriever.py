"""Variant registry. A variant = (retrieval layer, query layer). One config value picks it; one command reruns all."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import lru_cache, partial
from typing import Any

from rag.index.bm25 import BM25Index
from rag.index.vector import DenseIndex, Embedder, FastEmbedder, HashingEmbedder, OllamaEmbedder
from rag.rerank import LexicalReranker, OnnxCrossEncoderReranker, Reranker
from rag.variants import v0_naive, v1_decomposed, v8_corrective
from rag.variants.v0_naive import RetrievalQuery, SearchFn
from rag.variants.v2_hybrid import build_search as hybrid_search
from rag.variants.v2_hybrid import rrf
from rag.variants.v3_rerank import build_search as rerank_search


def dense_search(index: DenseIndex) -> SearchFn:
    async def s(q, k, filters=None):
        return await asyncio.to_thread(index.search, q, k, filters)
    return s


QueryFn = Callable[..., Any]
# name -> (retrieval layer, query layer)
VARIANTS: dict[str, tuple[str, QueryFn]] = {
    "v0_naive": ("dense", v0_naive.retrieve),
    "v1_decomposed": ("dense", v1_decomposed.retrieve),
    "v2_hybrid": ("hybrid", v0_naive.retrieve),
    "v3_rerank": ("rerank", v0_naive.retrieve),
    "v1_v2_hybrid_decomposed": ("hybrid", v1_decomposed.retrieve),
    "v1_v2_v3": ("hybrid_rerank", v1_decomposed.retrieve),
    "v8_corrective": ("hybrid", v8_corrective.retrieve),
}


class Retriever:
    def __init__(self, variant: str, search: SearchFn, query_fn: QueryFn | None = None):
        if variant not in VARIANTS:
            raise ValueError(f"unknown RAG variant {variant!r}; have {sorted(VARIANTS)}")
        self.variant, self.search, self.query_fn = variant, search, query_fn or VARIANTS[variant][1]

    async def retrieve(self, query: RetrievalQuery, k: int = 5) -> list[dict[str, Any]]:
        return await self.query_fn(query, self.search, k=k)


def make_embedder(cfg: dict):
    rag = cfg["rag"]
    if rag["embedder"] == "ollama":
        return OllamaEmbedder(rag["ollama_embed_model"])
    if rag["embedder"] == "fastembed":
        return FastEmbedder(rag["fastembed_model"], rag.get("fastembed_batch_size", 32),
                            rag.get("cache_dir"), rag.get("model_threads", 2))
    if rag["embedder"] == "hashing":
        return HashingEmbedder()
    raise ValueError(f"unknown embedder {rag['embedder']!r}; expected hashing, ollama, or fastembed")


@lru_cache(maxsize=4)
def _neural_reranker(model, cache_dir, threads):
    return OnnxCrossEncoderReranker(model, cache_dir, threads)


def make_reranker(cfg):
    rag = cfg["rag"]
    kind = rag.get("reranker", "lexical")
    if kind == "lexical":
        return LexicalReranker()
    if kind == "fastembed":
        return _neural_reranker(rag["reranker_model"], rag.get("cache_dir"), rag.get("model_threads", 2))
    raise ValueError(f"unknown reranker {kind!r}")


def local_search(index: DenseIndex) -> SearchFn:
    return dense_search(index)


def build_retriever(cfg: dict, items: list[dict[str, Any]], search: SearchFn | None = None,
                    reranker: Reranker | None = None, embedder: Embedder | None = None,
                    dense_index: DenseIndex | None = None) -> Retriever:
    variant = cfg["rag"]["variant"]
    query_fn = (partial(v8_corrective.retrieve, minimum_coverage=cfg['rag'].get('corrective_min_coverage', .5))
                if variant == 'v8_corrective' else None)
    if search is not None:                      # evidence behind the Portfolio MCP server: layers run server-side
        layer = VARIANTS[variant][0]
        async def remote(query, k, filters=None):
            return await search(query, k, {**(filters or {}), 'retrieval_layer': layer})
        return Retriever(variant, remote, query_fn)
    chunked = v0_naive.chunk_items(items, cfg['rag'].get('chunk_size', 1200), cfg['rag'].get('chunk_overlap', 150))
    if dense_index is not None and dense_index.items != chunked:
        dense_index = DenseIndex(chunked, dense_index.embedder)
    dense, bm25 = dense_index or DenseIndex(chunked, embedder or make_embedder(cfg)), BM25Index(chunked)
    layer = VARIANTS[variant][0]
    rr = reranker or (make_reranker(cfg) if layer in {"rerank", "hybrid_rerank"} else None)
    base = {"dense": dense_search(dense), "hybrid": hybrid_search(dense, bm25), "rerank": dense_search(dense)}.get(layer)
    if layer == "rerank":
        base = rerank_search(dense_search(dense), rr)
    if layer == "hybrid_rerank":
        base = rerank_search(hybrid_search(dense, bm25), rr)
    return Retriever(variant, base, query_fn)  # type: ignore[arg-type]


__all__ = ["Retriever", "RetrievalQuery", "build_retriever", "VARIANTS", "local_search", "make_embedder", "rrf"]
