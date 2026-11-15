from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from rag.index.vector import item_text


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+#.\-]*[a-z0-9+#]|[a-z0-9]", text.lower())


class BM25Index:
    """Exact-term matching: keeps 'Celery', 'dbt', 'Pinecone' sharp where embeddings blur them."""

    def __init__(self, items: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.items, self.k1, self.b = items, k1, b
        self.docs = [Counter(tokenize(item_text(i))) for i in items]
        self.len = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.len) / len(self.len) if items else 0.0
        df = Counter(t for d in self.docs for t in d)
        n = len(items)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, k: int = 5, filters: dict | None = None) -> list[dict[str, Any]]:
        q, scored = tokenize(query), []
        for i, (it, d, ln) in enumerate(zip(self.items, self.docs, self.len, strict=True)):
            if filters and any(it.get(f) != v for f, v in filters.items()):
                continue
            s = sum(self.idf.get(t, 0) * d[t] * (self.k1 + 1) / (d[t] + self.k1 * (1 - self.b + self.b * ln / (self.avg or 1)))
                    for t in q if t in d)
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [{**self.items[i], "score": s} for s, i in scored[:k]]
