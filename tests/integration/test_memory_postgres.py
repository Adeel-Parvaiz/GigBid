"""C2: promoted memory survives a new API/worker store connection."""
from __future__ import annotations

import asyncio
import os
import socket
from urllib.parse import urlsplit

import pytest

from agent.memory.store import MemoryManager
from agent.persistence import make_memory_store

URL = os.environ.get("TEST_DATABASE_URL", "postgresql://gigbid:gigbid@localhost:5432/gigbid")
ORIGINAL = "I am passionate about data. I built a churn model. I compared two classifiers."
EDITED = "I built a churn model. I compared two classifiers."


def postgres_reachable() -> bool:
    parsed = urlsplit(URL)
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 5432), timeout=0.5):
            return True
    except OSError:
        return False


async def _verify_memory_survives_store_recreation():
    if not postgres_reachable():
        pytest.skip("no Postgres listener")

    freelancer_id = f"memory-test-{os.urandom(8).hex()}"
    async with make_memory_store(URL) as store:
        memory = MemoryManager(store, promote_after=3, min_outcomes=5)
        for job_id in ("job-1", "job-2", "job-3"):
            await memory.observe_edit(freelancer_id, job_id, ORIGINAL, EDITED)
        for run_id, outcome in (
            ("run-1", "won"),
            ("run-2", "replied"),
            ("run-3", "ignored"),
            ("run-4", "ignored"),
            ("run-5", "ignored"),
        ):
            await memory.record_outcome(freelancer_id, "ml", outcome, event_id=run_id)

    async with make_memory_store(URL) as store:
        memory = MemoryManager(store, promote_after=3, min_outcomes=5)
        rules = await memory.list_style(freelancer_id)
        assert any(
            item["id"] == "cut_first_sentence"
            and item["learned_from_jobs"] == ["job-1", "job-2", "job-3"]
            for item in rules
        )
        assert await memory.outcome_memory(freelancer_id) == {
            "ml": {"n": 5, "reply_rate": 0.4, "win_rate": 0.2}
        }

        for rule in rules:
            await memory.delete_style(freelancer_id, rule["id"])
        await memory.delete_outcome(freelancer_id, "ml")
        assert await memory.list_style(freelancer_id) == []
        assert await memory.outcome_memory(freelancer_id) == {}


def test_promoted_style_and_outcome_memory_survive_store_recreation():
    loop = asyncio.SelectorEventLoop() if os.name == "nt" else asyncio.new_event_loop()
    try:
        loop.run_until_complete(_verify_memory_survives_store_recreation())
    finally:
        loop.close()
