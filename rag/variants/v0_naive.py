"""V0 baseline: one dense query with the whole job post, top-k cosine."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from rag.ingest.loaders import fixed_chunks

SearchFn = Callable[[str, int, dict | None], Awaitable[list[dict[str, Any]]]]


@dataclass
class RetrievalQuery:
    job_text: str
    requirements: list[str] = field(default_factory=list)
    filters: dict = field(default_factory=dict)


def chunk_items(items: list[dict], size=1200, overlap=150) -> list[dict]:
    """Fixed body chunks shared by variants, preserving attribution and original item ID."""
    result = []
    for item in items:
        parts = fixed_chunks(item.get('summary', ''), size, overlap)
        for position, text in enumerate(parts):
            eid = item['evidence_id'] if len(parts) == 1 else f"{item['evidence_id']}::chunk:{position}"
            result.append({**item, 'evidence_id': eid, 'parent_evidence_id': item.get('parent_evidence_id', item['evidence_id']),
                           'summary': text, 'chunk_index': item.get('chunk_index', position),
                           'persona': item.get('persona', item.get('freelancer_id')),
                           'project': item.get('project', item.get('project_id', item.get('title'))),
                           'client_industry': item.get('client_industry'), 'date': item.get('date'), 'outcome': item.get('outcome')})
    return result


async def retrieve(query: RetrievalQuery, search: SearchFn, k: int = 5):
    return await search(query.job_text, k, query.filters)
