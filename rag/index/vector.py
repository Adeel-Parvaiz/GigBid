from __future__ import annotations

import re
import zlib
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any, Protocol

import httpx
import numpy as np


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...


class HashingEmbedder:
    """Deterministic offline embedder (hashed words + char trigrams). For tests/CI only.
    Real runs use an open embedding model (OllamaEmbedder: nomic-embed-text / BGE-M3)."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            t = t.lower()
            feats = re.findall(r"[a-z0-9+#]+", t)
            feats += [t[j:j + 3] for j in range(len(t) - 2)]
            for f in feats:
                h = zlib.crc32(f.encode())
                out[i, h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


class OllamaEmbedder:
    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model, self.base_url = model, base_url

    def embed(self, texts: list[str]) -> np.ndarray:
        r = httpx.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": texts}, timeout=60)
        r.raise_for_status()
        v = np.array(r.json()["embeddings"], dtype=np.float32)
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)


class FastEmbedder:
    """Locally run an open ONNX embedding model through FastEmbed."""

    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2", batch_size: int = 32,
                 cache_dir: str | None = None, threads: int = 2):
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError("FastEmbed is optional; install the 'embeddings' extra to use it") from exc
        self.model = model
        self.batch_size = batch_size
        self._model = TextEmbedding(model_name=model, cache_dir=cache_dir, threads=threads,
                                    providers=["CPUExecutionProvider"])
        runtime_model = self._model.model
        model_dir = Path(runtime_model._model_dir)
        model_file = model_dir / runtime_model.model_description.model_file
        if not model_file.is_file():
            raise FileNotFoundError(f"FastEmbed model artifact not found: {model_file}")
        self.metadata = {
            "provider": "fastembed",
            "package_version": version("fastembed"),
            "model": model,
            "source": runtime_model.model_description.sources.hf,
            "revision": model_dir.name,
            "model_file": model_file.name,
            "model_file_sha256": sha256(model_file.read_bytes()).hexdigest(),
            "dimensions": runtime_model.model_description.dim,
            "license": runtime_model.model_description.license,
            "batch_size": batch_size,
        }

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        vectors = np.asarray(list(self._model.embed(texts, batch_size=self.batch_size)), dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(texts):
            raise ValueError(f"FastEmbed returned shape {vectors.shape} for {len(texts)} texts")
        return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)


def item_text(it: dict[str, Any]) -> str:
    return f"{it.get('title', '')}. {it.get('summary', '')} Skills: {', '.join(it.get('skills', []))}"


class DenseIndex:
    def __init__(self, items: list[dict[str, Any]], embedder: Embedder):
        self.items, self.embedder = items, embedder
        self.vecs = embedder.embed([item_text(i) for i in items]) if items else np.zeros((0, 1))

    def update(self, items: list[dict[str, Any]], precomputed: dict | None = None):
        """Keep unchanged vectors; embed only additions/edits and remove deleted IDs."""
        previous = {it['evidence_id']: (item_text(it), self.vecs[n]) for n, it in enumerate(self.items)}
        vectors, pending = {}, []
        for it in items:
            eid = it['evidence_id']
            if eid in previous and previous[eid][0] == item_text(it):
                vectors[eid] = previous[eid][1]
            elif precomputed and eid in precomputed:
                vectors[eid] = np.asarray(precomputed[eid], dtype=np.float32)
            else:
                pending.append(it)
        if pending:
            for it, vector in zip(pending, self.embedder.embed([item_text(i) for i in pending]), strict=True):
                vectors[it['evidence_id']] = vector
        self.items = items
        self.vecs = np.asarray([vectors[i['evidence_id']] for i in items]) if items else np.zeros((0, 1))

    def search(self, query: str, k: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self.items:
            return []
        sims = self.vecs @ self.embedder.embed([query])[0]
        order = np.argsort(-sims)
        out = []
        for idx in order:
            it = self.items[idx]
            if filters and any(it.get(f) != v for f, v in filters.items()):
                continue
            out.append({**it, "score": float(sims[idx])})
            if len(out) == k:
                break
        return out
