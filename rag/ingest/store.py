"""Encrypted, user-scoped documents and persistent incremental chunk embeddings."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field, model_validator

from rag.index.vector import HashingEmbedder, item_text
from rag.ingest.loaders import fixed_chunks, load_document


class DocumentMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    project: str = Field(min_length=1, max_length=200)
    skills: list[str] = Field(default_factory=list, max_length=50)
    date: str | None = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    client_industry: str | None = Field(None, max_length=200)
    outcome: str | None = Field(None, max_length=1000)
    provenance: str = Field('user-upload', pattern='^(user-upload|synthetic)$')
    authorship_confirmed: bool = False

    @model_validator(mode='after')
    def valid_metadata(self):
        from datetime import date
        if self.date:
            date.fromisoformat(self.date)
        if not self.authorship_confirmed:
            raise ValueError('Confirm that you may use this material as your portfolio evidence')
        if any(not skill.strip() or len(skill) > 100 for skill in self.skills):
            raise ValueError('Skills must be nonempty and at most 100 characters each')
        return self


class PortfolioCorpus:
    def __init__(self, vault):
        self.vault = vault

    def documents(self, user):
        return self.vault.list_prefix(user, 'portfolio:document:')

    def ingest(self, user, persona, filename, content, kind, metadata, source=None):
        metadata = DocumentMetadata.model_validate(metadata)
        if kind == 'past_proposal' and not metadata.outcome:
            raise ValueError('Past proposals require an outcome (use unknown if unavailable)')
        text = load_document(filename, content, kind)
        source = source or 'upload:' + filename
        document_id = hashlib.sha256(f'{user}|{persona}|{kind}|{source}'.encode()).hexdigest()[:24]
        key = 'portfolio:document:' + document_id
        old = self.vault.get(user, key, {})
        digest = hashlib.sha256(json.dumps({'text': text, 'metadata': metadata.model_dump()}, sort_keys=True).encode()).hexdigest()
        if old.get('digest') == digest:
            return {**self.summary(old), 'unchanged': True, 'embedded_chunks': 0}
        previous = {c['evidence_id']: c for c in old.get('chunks', [])}
        chunks, seen, changed = [], {}, []
        common = {**metadata.model_dump(exclude={'authorship_confirmed'}), 'persona': persona,
                  'freelancer_id': persona, 'type': kind, 'source': source, 'document_id': document_id,
                  'provenance': ('synthetic' if metadata.provenance == 'synthetic' else
                                 'real-github-mcp' if source.startswith('https://github.com/') else metadata.provenance),
                  'ingestion_method': 'github-mcp' if source.startswith('https://github.com/') else 'upload',
                  'authorship_confirmed_by_user': True, 'limitations': 'User-supplied source evidence; outcomes and authorship are user-reported, not independently verified.'}
        for position, chunk in enumerate(fixed_chunks(text)):
            chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()[:20]
            occurrence = seen.get(chunk_hash, 0)
            seen[chunk_hash] = occurrence + 1
            eid = f'chunk-{document_id}-{chunk_hash}-{occurrence}'
            item = {**common, 'evidence_id': eid, 'summary': chunk, 'chunk_index': position,
                    'content_sha256': hashlib.sha256(chunk.encode()).hexdigest()}
            if eid in previous and item_text(previous[eid]) == item_text(item):
                item['vector'] = previous[eid]['vector']
            else:
                changed.append(item)
            chunks.append(item)
        if changed:
            vectors = HashingEmbedder().embed([item_text(c) for c in changed])
            for item, vector in zip(changed, vectors, strict=True):
                item['vector'] = vector.tolist()
        document = {'document_id': document_id, 'filename': filename, 'type': kind, 'persona': persona,
                    'metadata': metadata.model_dump(), 'source': source, 'digest': digest, 'chunks': chunks,
                    'revision': old.get('revision', 0) + 1, 'updated_at': datetime.now(UTC).isoformat(),
                    'embedding': 'hashing-512-v1'}
        # One encrypted record transaction replaces the document and its full chunk/vector set atomically.
        self.vault.put(user, key, document)
        return {**self.summary(document), 'unchanged': False, 'embedded_chunks': len(changed)}

    @staticmethod
    def summary(document):
        return {k: v for k, v in document.items() if k != 'chunks'} | {'chunk_count': len(document['chunks'])}

    def delete(self, user, document_id):
        document = self.vault.get(user, 'portfolio:document:' + document_id)
        if not document:
            raise ValueError('Document not found')
        self.vault.delete(user, 'portfolio:document:' + document_id)
        for legacy in self.vault.list_prefix(user, 'github:evidence:'):
            if legacy['source'] == document['source']:
                self.vault.delete(user, 'github:evidence:' + legacy['evidence_id'])
