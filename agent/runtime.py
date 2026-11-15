from __future__ import annotations

import json
from pathlib import Path

from langgraph.store.base import BaseStore

from agent.config import load_config
from agent.deps import Deps
from agent.llm import build_llm
from agent.marketplace_mcp import build_mcp_port
from agent.mcp_client import AgentTools, user_portfolio_search, workspace_connection
from agent.memory.store import MemoryManager
from agent.workspace_mcp import McpWorkspace
from mcp_servers.marketplace.adapters.sample import DATA, SampleAdapter
from rag.index.vector import DenseIndex, Embedder
from rag.retriever import build_retriever


def load_sample_profile(freelancer_id: str | None = None, data_dir=None) -> dict:
    rows = json.loads((Path(data_dir or DATA) / "freelancers.json").read_text())
    return next(r for r in rows if freelancer_id is None or r["freelancer_id"] == freelancer_id)


def build_deps(cfg: dict | None = None, port=None, llm=None, data_dir=None, embedder: Embedder | None = None,
               dense_index: DenseIndex | None = None, reranker=None, workspace=None,
               memory_store: BaseStore | None = None) -> Deps:
    cfg = cfg or load_config()
    if workspace is None and cfg['workspace']['source'] != 'mcp':
        raise ValueError('Application workspace access requires MCP; inject a workspace double explicitly in tests.')
    data_path = Path(data_dir or DATA)
    items = json.loads((data_path / "portfolio_items.json").read_text())
    search = None
    if cfg["portfolio"]["source"] == "mcp":      # evidence only via the Portfolio MCP server
        search = user_portfolio_search(cfg)
    return Deps(port=port or (build_mcp_port(cfg) if cfg["marketplace"]["mode"] == "mcp" else SampleAdapter(data_path)),
                retriever=build_retriever(cfg, items, search, embedder=embedder, dense_index=dense_index, reranker=reranker),
                llm=llm or build_llm(cfg), cfg=cfg, workspace=(workspace if workspace is not None else McpWorkspace(AgentTools({"workspace": workspace_connection(cfg)}))),
                memory=MemoryManager(memory_store, promote_after=cfg["memory"]["promote_after"],
                                     min_outcomes=cfg["memory"]["min_outcomes"]))
