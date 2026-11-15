"""Long-term, user-scoped memory. Only promoted, deletable items live here."""
from __future__ import annotations

import hashlib
from collections import Counter

from langgraph.store.base import BaseStore, SearchItem
from langgraph.store.memory import InMemoryStore

from agent.memory.promotion_rules import extract_signals, rule_text


class MemoryManager:
    def __init__(self, store: BaseStore | None = None, promote_after: int = 3, min_outcomes: int = 5):
        if promote_after < 1 or min_outcomes < 1:
            raise ValueError("memory promotion thresholds must be positive")
        self.store = store if store is not None else InMemoryStore()
        self.promote_after, self.min_outcomes = promote_after, min_outcomes

    @staticmethod
    def _key(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _namespace(self, freelancer_id: str, kind: str, item: str | None = None) -> tuple[str, ...]:
        namespace = ("gigbid_memory", self._key(freelancer_id), kind)
        return namespace if item is None else (*namespace, self._key(item))

    async def _all(self, namespace: tuple[str, ...]) -> list[SearchItem]:
        items: list[SearchItem] = []
        offset, page_size = 0, 500
        while True:
            page = await self.store.asearch(namespace, limit=page_size, offset=offset)
            items.extend(page)
            if len(page) < page_size:
                return items
            offset += len(page)

    async def observe_edit(self, freelancer_id: str, job_id: str, original: str, edited: str) -> list[str]:
        promoted: list[str] = []
        style_namespace = self._namespace(freelancer_id, "style")
        for signal in extract_signals(original, edited):
            signal_key = self._key(signal)
            if await self.store.aget(style_namespace, signal_key):
                continue

            candidates_namespace = self._namespace(freelancer_id, "style_candidates", signal)
            job_key = self._key(job_id)
            if not await self.store.aget(candidates_namespace, job_key):
                await self.store.aput(candidates_namespace, job_key, {"job_id": job_id})

            candidates = await self.store.asearch(candidates_namespace, limit=self.promote_after)
            jobs = sorted({item.value["job_id"] for item in candidates})
            if len(jobs) < self.promote_after:
                continue
            if not await self.store.aget(style_namespace, signal_key):
                await self.store.aput(
                    style_namespace,
                    signal_key,
                    {"id": signal, "rule": rule_text(signal), "learned_from_jobs": jobs[: self.promote_after]},
                )
                promoted.append(signal)
        return promoted

    async def style_rules(self, freelancer_id: str) -> list[str]:
        items = await self.store.asearch(self._namespace(freelancer_id, "style"), limit=100)
        return [item.value["rule"] for item in sorted(items, key=lambda item: item.value["id"])]

    async def list_style(self, freelancer_id: str) -> list[dict]:
        items = await self.store.asearch(self._namespace(freelancer_id, "style"), limit=100)
        return [item.value for item in sorted(items, key=lambda item: item.value["id"])]

    async def delete_style(self, freelancer_id: str, rule_id: str) -> None:
        await self.store.adelete(self._namespace(freelancer_id, "style"), self._key(rule_id))
        candidates_namespace = self._namespace(freelancer_id, "style_candidates", rule_id)
        for item in await self._all(candidates_namespace):
            await self.store.adelete(candidates_namespace, item.key)

    async def record_outcome(self, freelancer_id: str, category: str, outcome: str, event_id: str) -> None:
        if outcome not in {"won", "replied", "ignored"}:
            raise ValueError(f"unsupported outcome: {outcome}")
        if not event_id:
            raise ValueError("outcome event_id must not be empty")

        events_namespace = self._namespace(freelancer_id, "outcome_events")
        await self.store.aput(events_namespace, self._key(event_id), {"category": category, "outcome": outcome})

    async def outcome_memory(self, freelancer_id: str) -> dict[str, dict]:
        events = await self._all(self._namespace(freelancer_id, "outcome_events"))
        counts_by_category: dict[str, Counter[str]] = {}
        for event in events:
            category_counts = counts_by_category.setdefault(event.value["category"], Counter())
            category_counts[event.value["outcome"]] += 1
        result = {}
        for category, counts in counts_by_category.items():
            n = sum(counts.values())
            if n >= self.min_outcomes:
                result[category] = {
                    "n": n,
                    "reply_rate": round((counts["won"] + counts["replied"]) / n, 3),
                    "win_rate": round(counts["won"] / n, 3),
                }
        return result

    async def delete_outcome(self, freelancer_id: str, category: str) -> None:
        events_namespace = self._namespace(freelancer_id, "outcome_events")
        events = await self._all(events_namespace)
        for item in events:
            if item.value["category"] == category:
                await self.store.adelete(events_namespace, item.key)
