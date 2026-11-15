"""Checkpointer factory. Postgres in compose/prod, SQLite file for quick local runs, memory for unit tests."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from langgraph.store.base import BaseStore


@asynccontextmanager
async def make_checkpointer(url: str | None):
    if url and url.startswith("postgres"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        async with AsyncPostgresSaver.from_conn_string(url) as saver:
            await saver.setup()
            yield saver
    elif url and url.startswith("sqlite"):
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        async with AsyncSqliteSaver.from_conn_string(url.removeprefix("sqlite:///")) as saver:
            await saver.setup()
            yield saver
    else:
        from langgraph.checkpoint.memory import InMemorySaver
        yield InMemorySaver()


@asynccontextmanager
async def make_memory_store(url: str | None) -> AsyncGenerator[BaseStore, None]:
    """Use durable PostgreSQL memory when configured; reserve InMemoryStore for local/test runs."""
    if url:
        if not url.startswith(("postgres://", "postgresql://")):
            raise ValueError("persistent memory requires a PostgreSQL DATABASE_URL")
        from langgraph.store.postgres import AsyncPostgresStore

        async with AsyncPostgresStore.from_conn_string(url) as store:
            await store.setup()
            yield store
        return

    from langgraph.store.memory import InMemoryStore

    yield InMemoryStore()
