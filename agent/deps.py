from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.llm import LLM
from agent.marketplace_port import MarketplacePort


@dataclass
class Deps:
    port: MarketplacePort
    retriever: Any   # rag.retriever.Retriever (will be fronted by the Portfolio MCP server)
    llm: LLM
    cfg: dict
    workspace: Any = None   # Workspace tools (local service or MCP)
    memory: Any = None      # agent.memory.store.MemoryManager
