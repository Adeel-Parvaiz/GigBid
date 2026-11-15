from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np

from rag.index.vector import Embedder, item_text


class SQLiteDenseIndex:
    """Persistent encrypted vectors with the same search contract as DenseIndex."""

    def __init__(self, items: list[dict[str, Any]], embedder: Embedder, database: str | Path,
                 namespace: str, cipher):
        self.embedder, self.namespace, self.cipher = embedder, namespace, cipher
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS portfolio_vectors ("
                "namespace TEXT NOT NULL, evidence_id TEXT NOT NULL, payload BLOB NOT NULL, "
                "PRIMARY KEY(namespace, evidence_id))"
            )
        self.items: list[dict[str, Any]] = []
        self.update(items)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.database, timeout=15)
        db.execute("PRAGMA busy_timeout=15000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _decode(self, payload: bytes) -> dict[str, Any]:
        return json.loads(self.cipher.decrypt(payload))

    def update(self, items: list[dict[str, Any]], precomputed: dict | None = None) -> None:
        identifiers = [item["evidence_id"] for item in items]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Portfolio index evidence IDs must be unique")

        with self._connection() as db:
            existing = {
                row[0]: self._decode(row[1])
                for row in db.execute(
                    "SELECT evidence_id, payload FROM portfolio_vectors WHERE namespace=?",
                    (self.namespace,),
                )
            }

        vectors: dict[str, np.ndarray] = {}
        pending: list[dict[str, Any]] = []
        fingerprints: dict[str, str] = {}
        for item in items:
            evidence_id = item["evidence_id"]
            fingerprint = hashlib.sha256(item_text(item).encode()).hexdigest()
            fingerprints[evidence_id] = fingerprint
            previous = existing.get(evidence_id)
            if previous and previous["text_sha256"] == fingerprint:
                vectors[evidence_id] = np.asarray(previous["vector"], dtype=np.float32)
            elif precomputed and evidence_id in precomputed:
                vectors[evidence_id] = np.asarray(precomputed[evidence_id], dtype=np.float32)
            else:
                pending.append(item)

        if pending:
            embedded = self.embedder.embed([item_text(item) for item in pending])
            if embedded.ndim != 2 or embedded.shape[0] != len(pending):
                raise ValueError("Portfolio embedder returned an invalid vector batch")
            for item, vector in zip(pending, embedded, strict=True):
                vectors[item["evidence_id"]] = np.asarray(vector, dtype=np.float32)

        payloads = []
        for item in items:
            evidence_id = item["evidence_id"]
            vector = vectors[evidence_id]
            if vector.ndim != 1 or not np.isfinite(vector).all():
                raise ValueError(f"Invalid portfolio vector for {evidence_id}")
            record = {"text_sha256": fingerprints[evidence_id], "item": item, "vector": vector.tolist()}
            payloads.append((
                self.namespace,
                evidence_id,
                self.cipher.encrypt(json.dumps(record, separators=(",", ":"), ensure_ascii=False).encode()),
            ))

        retained = set(identifiers)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            stale = [
                row[0] for row in db.execute(
                    "SELECT evidence_id FROM portfolio_vectors WHERE namespace=?",
                    (self.namespace,),
                ) if row[0] not in retained
            ]
            db.executemany(
                "DELETE FROM portfolio_vectors WHERE namespace=? AND evidence_id=?",
                [(self.namespace, evidence_id) for evidence_id in stale],
            )
            db.executemany(
                "INSERT INTO portfolio_vectors(namespace,evidence_id,payload) VALUES (?,?,?) "
                "ON CONFLICT(namespace,evidence_id) DO UPDATE SET payload=excluded.payload",
                payloads,
            )
            db.commit()
        self.items = list(items)

    def search(self, query: str, k: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self.items or k <= 0:
            return []
        query_vector = self.embedder.embed([query])[0]
        matches = []
        with self._connection() as db:
            rows = db.execute(
                "SELECT payload FROM portfolio_vectors WHERE namespace=?",
                (self.namespace,),
            )
            for (sealed,) in rows:
                record = self._decode(sealed)
                item = record["item"]
                if filters and any(item.get(field) != value for field, value in filters.items()):
                    continue
                vector = np.asarray(record["vector"], dtype=np.float32)
                if vector.shape != query_vector.shape:
                    raise ValueError("Portfolio index vector dimension does not match the query embedder")
                matches.append({**item, "score": float(vector @ query_vector)})
        matches.sort(key=lambda item: item["score"], reverse=True)
        return matches[:k]
