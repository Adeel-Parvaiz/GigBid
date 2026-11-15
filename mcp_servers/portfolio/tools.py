"""Portfolio store + tool logic (read-only). server.py only registers these with MCP."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rag.index.bm25 import BM25Index
from rag.index.sqlite_vector import SQLiteDenseIndex
from rag.index.vector import DenseIndex, Embedder, HashingEmbedder
from rag.rerank import LexicalReranker

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "sample"
ItemType = Literal["case_study", "past_proposal", "cv", "readme", "code", "review"]


class SearchFilters(BaseModel):
    type: ItemType | None = Field(None, description="Restrict to one item type. Past proposals are excluded unless asked for.")
    skill: str | None = Field(None, description="Only items listing this skill (case-insensitive).")
    freelancer_id: str | None = Field(None, description="Whose portfolio. Defaults to the server's bound freelancer.")
    retrieval_layer: Literal['dense', 'hybrid', 'rerank', 'hybrid_rerank'] | None = Field(None, description='B2 retrieval layer; query decomposition remains client-side.')


class EvidenceItem(BaseModel):
    evidence_id: str
    type: str
    title: str
    summary: str
    skills: list[str]
    source: str
    date: str | None = None
    outcome: str | None = None
    freelancer_id: str
    parent_evidence_id: str | None = None
    persona: str | None = None
    project: str | None = None
    client_industry: str | None = None
    document_id: str | None = None
    chunk_index: int | None = None
    provenance: str | None = None
    limitations: str | None = None
    score: float = 0.0


class SearchEvidenceResult(BaseModel):
    items: list[EvidenceItem]


class SkillCount(BaseModel):
    skill: str
    items: int


class SkillList(BaseModel):
    skills: list[SkillCount]


class TenantError(ValueError):
    pass


class PortfolioStore:
    def __init__(self, data_dir: Path | str | None = None, freelancer_id: str | None = None,
                 embedder: Embedder | None = None, layer: str | None = None, user_id=None, vault=None):
        d = Path(data_dir or os.environ.get("PORTFOLIO_DIR") or os.environ.get("GIGBID_DATA_DIR") or DEFAULT_DIR)
        self.bound = freelancer_id or os.environ.get("PORTFOLIO_FREELANCER_ID")
        cases = json.loads((d / "portfolio_items.json").read_text())
        props = json.loads((d / "past_proposals.json").read_text()) if (d / "past_proposals.json").exists() else []
        for p in props:
            p["evidence_id"] = p.pop("proposal_id")
        from rag.variants.v0_naive import chunk_items
        self.rag_config = json.loads(os.environ.get('PORTFOLIO_RAG_CONFIG', '{}'))
        self.full_items = {i['evidence_id']: i for i in cases + props}
        self.base_full_items = dict(self.full_items)
        self.items = {i['evidence_id']: i for i in chunk_items(cases + props,
            self.rag_config.get('chunk_size', 1200), self.rag_config.get('chunk_overlap', 150))}
        self.user = user_id or os.environ.get('PORTFOLIO_USER_ID')
        self.vault = vault
        if self.user and self.vault is None:
            from apps.api.auth.oauth_store import OAuthVault
            self.vault = OAuthVault()
        self.base_items = dict(self.items)
        for item in self.base_items.values():
            item.setdefault('persona', item['freelancer_id'])
            item.setdefault('project', item.get('project_id') or item['title'])
            item.setdefault('client_industry', None)
        if embedder is None and self.rag_config.get('embedder') in {'fastembed', 'ollama'}:
            from agent.config import load_config
            from rag.retriever import make_embedder
            embedder = make_embedder(load_config(overrides={'rag': self.rag_config}))
        vector_embedder = embedder or HashingEmbedder()
        if self.user and self.vault:
            index_database = os.environ.get("PORTFOLIO_INDEX_DB") or str(
                self.vault.database.with_name("portfolio_index.sqlite")
            )
            self.index = SQLiteDenseIndex(
                list(self.items.values()), vector_embedder, index_database, self.user, self.vault.cipher
            )
        else:
            self.index = DenseIndex(list(self.items.values()), vector_embedder)
        self.bm25 = BM25Index(list(self.items.values()))
        self.layer = layer or os.environ.get("PORTFOLIO_RETRIEVAL", "dense")      # dense | hybrid | hybrid_rerank
        self.reranker = LexicalReranker()
        self._configured_reranker = False
        self._import_digest = None
        self._refresh()

    def _refresh(self):
        if not self.user:
            return
        imported = self.vault.list_prefix(self.user, 'github:evidence:')
        documents = self.vault.list_prefix(self.user, 'portfolio:document:')
        digest = [(i['evidence_id'], i.get('content_sha256')) for i in imported] + [(d['document_id'], d['digest']) for d in documents]
        if digest == self._import_digest:
            return
        items, vectors = dict(self.base_items), {}
        self.full_items = dict(self.base_full_items)
        chunked_sources = {d['source'] for d in documents}
        for item in imported:
            self.full_items[item['evidence_id']] = item
            if item['source'] in chunked_sources:
                continue
            item.setdefault('persona', item['freelancer_id'])
            item.setdefault('project', item['title'])
            item.setdefault('client_industry', None)
            from rag.variants.v0_naive import chunk_items
            for part in chunk_items([item], self.rag_config.get('chunk_size', 1200), self.rag_config.get('chunk_overlap', 150)):
                items[part['evidence_id']] = part
        for doc in documents:
            for chunk in doc['chunks']:
                item = {k: v for k, v in chunk.items() if k != 'vector'}
                items[item['evidence_id']] = item
                if isinstance(self.index.embedder, HashingEmbedder):
                    vectors[item['evidence_id']] = chunk['vector']
        self.index.update(list(items.values()), vectors)
        self.items = items
        self.bm25 = BM25Index(list(items.values()))
        self._import_digest = digest

    def _owner(self, requested: str | None) -> str | None:
        if self.bound and requested and requested != self.bound:
            raise TenantError("freelancer_id does not match this server's bound portfolio")
        return requested or self.bound

    def _visible(self, item_id: str, owner: str | None) -> dict:
        it = self.items.get(item_id) or self.full_items.get(item_id)
        if it is None or (owner and it["freelancer_id"] != owner):
            raise ValueError(f"unknown id {item_id!r}")
        return it

    def _raw(self, q: str, filters: dict | None, layer: str | None = None) -> list[dict]:
        """Server-side retrieval layer (V2 hybrid / V3 rerank). Query decomposition (V1) is the caller's job."""
        n = len(self.items)
        layer = layer or self.layer
        if layer == "dense":
            return self.index.search(q, n, filters)
        from rag.retriever import rrf
        hits = (self.index.search(q, 20, filters) if layer == 'rerank' else
                rrf([self.index.search(q, 20, filters), self.bm25.search(q, 20, filters)], n))
        if layer in {'rerank', 'hybrid_rerank'} and hits:
            if not self._configured_reranker:
                from agent.config import load_config
                from rag.retriever import make_reranker
                self.reranker = make_reranker(load_config(overrides={'rag': self.rag_config}))
                self._configured_reranker = True
            texts = [f"{h['title']}. {h['summary']} {' '.join(h['skills'])}" for h in hits]
            hits = [hits[i] for _, i in sorted(zip(self.reranker.score(q, texts), range(len(hits)), strict=True), key=lambda x: -x[0])]
        return hits

    def search_evidence(self, requirement: str, k: int = 5, filters: SearchFilters | None = None) -> SearchEvidenceResult:
        self._refresh()
        f = filters or SearchFilters()
        owner = self._owner(f.freelancer_id)
        raw_filters = {'freelancer_id': owner} if owner else {}
        if f.type:
            raw_filters['type'] = f.type
        raw = self._raw(requirement, raw_filters or None, f.retrieval_layer)
        out = []
        for h in raw:
            if f.type is None and h["type"] == "past_proposal":
                continue
            if f.type and h["type"] != f.type:
                continue
            if f.skill and f.skill.lower() not in [s.lower() for s in h["skills"]]:
                continue
            out.append(EvidenceItem(**{x: h.get(x) for x in EvidenceItem.model_fields if x in h}))
            if len(out) == k:
                break
        return SearchEvidenceResult(items=out)

    def get_case_study(self, case_id: str, freelancer_id: str | None = None) -> EvidenceItem:
        self._refresh()
        it = self._visible(case_id, self._owner(freelancer_id))
        return EvidenceItem(**{x: it.get(x) for x in EvidenceItem.model_fields if x in it})

    def list_skills(self, freelancer_id: str | None = None) -> SkillList:
        self._refresh()
        owner, counts = self._owner(freelancer_id), {}
        for it in self.items.values():
            if owner and it["freelancer_id"] != owner:
                continue
            for s in it["skills"]:
                counts[s] = counts.get(s, 0) + 1
        return SkillList(skills=[SkillCount(skill=s, items=n) for s, n in sorted(counts.items())])
