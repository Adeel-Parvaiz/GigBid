"""Cross-encoder reranking (V3). The lexical reranker is a dependency-free stand-in for tests/CI only."""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from importlib.metadata import version
from pathlib import Path
from threading import RLock
from typing import Protocol

from rag.index.bm25 import tokenize


class Reranker(Protocol):
    def score(self, query: str, docs: list[str]) -> list[float]: ...


class LexicalReranker:
    def score(self, query: str, docs: list[str]) -> list[float]:
        q = set(tokenize(query))
        return [len(q & set(tokenize(d))) / (len(q) or 1) for d in docs]


class CrossEncoderReranker:
    """bge-reranker-v2-m3 on CPU. Needs `pip install sentence-transformers`; untested in this repo's CI."""

    def __init__(self, model: str = "BAAI/bge-reranker-v2-m3"):
        from sentence_transformers import CrossEncoder
        self.m = CrossEncoder(model)

    def score(self, query: str, docs: list[str]) -> list[float]:
        return [float(x) for x in self.m.predict([(query, d) for d in docs])]


class OnnxCrossEncoderReranker:
    """Actual open cross-encoder inference through FastEmbed, with bounded pair caching."""

    def __init__(self, model="Xenova/ms-marco-MiniLM-L-6-v2", cache_dir=None, threads=2):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.model = TextCrossEncoder(model_name=model, cache_dir=cache_dir, threads=threads,
                                      providers=["CPUExecutionProvider"])
        runtime = self.model.model
        directory = Path(runtime._model_dir)
        artifact = directory / runtime.model_description.model_file
        self.metadata = {"provider": "fastembed-cross-encoder", "package_version": version("fastembed"),
                         "model": model, "source": runtime.model_description.sources.hf,
                         "revision": directory.name, "model_file": runtime.model_description.model_file,
                         "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                         "license": runtime.model_description.license, "threads": threads, "pair_cache_limit": 8192}
        self.cache = OrderedDict()
        self.lock = RLock()

    def score(self, query: str, docs: list[str]) -> list[float]:
        if not docs:
            return []
        with self.lock:
            missing = list(dict.fromkeys(doc for doc in docs if (query, doc) not in self.cache))
            scores = list(self.model.rerank(query, missing, batch_size=32)) if missing else []
            if len(scores) != len(missing):
                raise ValueError("Cross-encoder returned an incomplete batch")
            for doc, score in zip(missing, scores, strict=True):
                self.cache[query, doc] = float(score)
            result = [self.cache[query, doc] for doc in docs]
            for doc in docs:
                self.cache.move_to_end((query, doc))
            while len(self.cache) > 8192:
                self.cache.popitem(last=False)
            return result
