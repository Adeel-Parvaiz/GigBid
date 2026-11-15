import io

import numpy as np
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from apps.api.auth.oauth_store import OAuthVault
from mcp_servers.portfolio.server import build_server
from mcp_servers.portfolio.tools import PortfolioStore
from rag.index.sqlite_vector import SQLiteDenseIndex
from rag.index.vector import DenseIndex, HashingEmbedder
from rag.ingest.loaders import fixed_chunks, load_document
from rag.ingest.store import PortfolioCorpus

META = {'title': 'Measured project', 'project': 'Example project', 'skills': ['Python'],
        'date': '2026-11-14', 'client_industry': 'retail', 'outcome': None,
        'provenance': 'synthetic', 'authorship_confirmed': True}


def text_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(600, 800)
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
        NameObject('/F1'): DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 50 700 Td (Python CV portfolio experience) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_loaders_extract_pdf_markdown_code_reviews_and_proposals():
    assert 'Python CV' in load_document('cv.pdf', text_pdf(), 'cv')
    assert load_document('case.md', b'# Reproducible case', 'case_study').startswith('#')
    assert 'def run' in load_document('main.py', b'def run(): return 1', 'code')
    assert load_document('reviews.json', b'[{"text":"Reliable delivery"}]', 'review') == 'Reliable delivery'
    assert load_document('proposal.json', b'{"text":"I propose a measured baseline"}', 'past_proposal')
    for filename, content, kind in [('image.pdf', b'not a pdf', 'cv'), ('secret.env', b'x', 'code'),
                                     ('large.md', b'x' * 2_000_001, 'case_study'), ('empty.md', b' ', 'case_study')]:
        with pytest.raises(ValueError):
            load_document(filename, content, kind)
    assert len(fixed_chunks('x' * 2400)) == 3


def test_ingestion_reuses_unchanged_chunks_and_preserves_required_metadata(tmp_path):
    corpus = PortfolioCorpus(OAuthVault(tmp_path / 'corpus.sqlite'))
    text = 'First section Python. ' * 120 + 'Ending original.'
    corpus.ingest('alice', 'sample-ai-engineer', 'case.md', text.encode(), 'case_study', META)
    again = corpus.ingest('alice', 'sample-ai-engineer', 'case.md', text.encode(), 'case_study', META)
    assert again['unchanged'] and again['embedded_chunks'] == 0 and again['revision'] == 1
    before = corpus.documents('alice')[0]['chunks']
    updated = corpus.ingest('alice', 'sample-ai-engineer', 'case.md', (text + ' Updated ending.').encode(), 'case_study', META)
    assert updated['revision'] == 2 and 0 < updated['embedded_chunks'] < updated['chunk_count']
    after = corpus.documents('alice')[0]['chunks']
    assert before[0]['vector'] == after[0]['vector']
    assert {'persona', 'type', 'project', 'skills', 'date', 'client_industry', 'outcome', 'source'} <= after[0].keys()
    assert after[0]['provenance'] == 'synthetic'
    assert corpus.documents('bob') == []
    with pytest.raises(ValueError, match='outcome'):
        corpus.ingest('alice', 'sample-ai-engineer', 'proposal.txt', b'An old proposal', 'past_proposal', META)


def test_dense_update_embeds_only_changed_items():
    class Counted(HashingEmbedder):
        def __init__(self):
            super().__init__()
            self.batches = []

        def embed(self, texts):
            self.batches.append(len(texts))
            return super().embed(texts)
    def item(eid, text):
        return {'evidence_id': eid, 'title': eid, 'summary': text, 'skills': []}
    model = Counted()
    index = DenseIndex([item('a', 'old'), item('b', 'same')], model)
    old_b = index.vecs[1].copy()
    index.update([item('a', 'changed'), item('b', 'same'), item('c', 'new')])
    assert model.batches == [2, 2] and np.array_equal(index.vecs[1], old_b)
    index.update([item('b', 'same')])
    assert model.batches == [2, 2] and len(index.items) == 1


async def test_open_mcp_session_refreshes_after_add_update_delete_and_restart(tmp_path):
    vault = OAuthVault(tmp_path / 'live.sqlite')
    corpus = PortfolioCorpus(vault)
    store = PortfolioStore(freelancer_id='sample-ai-engineer', user_id='alice', vault=vault)
    assert isinstance(store.index, SQLiteDenseIndex)
    assert (tmp_path / 'portfolio_index.sqlite').is_file()
    async with connect(build_server(store)) as session:
        before = await session.call_tool('search_evidence', {'requirement': 'uniqueb1marker'})
        assert not any('uniqueb1marker' in i['summary'] for i in before.structuredContent['items'])
        result = corpus.ingest('alice', 'sample-ai-engineer', 'new.md', b'uniqueb1marker Python validation work', 'case_study', META)
        eid = corpus.documents('alice')[0]['chunks'][0]['evidence_id']
        found = await session.call_tool('get_case_study', {'id': eid})
        assert found.structuredContent['project'] == META['project']
        assert found.structuredContent['persona'] == 'sample-ai-engineer'
        # A second server reading the same encrypted store also sees persisted evidence.
        restarted = PortfolioStore(freelancer_id='sample-ai-engineer', user_id='alice', vault=OAuthVault(vault.database))
        assert restarted.get_case_study(eid).source == 'upload:new.md'
        assert any(
            item['evidence_id'] == eid
            for item in restarted.index.search('uniqueb1marker', k=10)
        )
        other = PortfolioStore(freelancer_id='sample-ai-engineer', user_id='bob', vault=vault)
        with pytest.raises(ValueError):
            other.get_case_study(eid)
        assert all(
            item['evidence_id'] != eid
            for item in other.index.search('uniqueb1marker', k=20)
        )
        corpus.ingest('alice', 'sample-ai-engineer', 'new.md', b'Replacement evidence without the old unique marker', 'case_study', META)
        assert (await session.call_tool('get_case_study', {'id': eid})).isError
        corpus.delete('alice', result['document_id'])
        assert not corpus.documents('alice')
