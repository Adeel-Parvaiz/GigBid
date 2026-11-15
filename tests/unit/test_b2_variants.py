import pytest

from agent.config import load_config
from rag.retriever import RetrievalQuery, build_retriever
from rag.variants.v0_naive import chunk_items
from rag.variants.v2_hybrid import rrf
from rag.variants.v8_corrective import retrieve_with_trace


def test_fixed_chunks_preserve_ownership_sources_and_original_item_id():
    item = {'evidence_id': 'project-a', 'summary': 'x' * 2600, 'title': 'A', 'skills': ['Celery'],
            'freelancer_id': 'alice', 'source': 'repo', 'type': 'code'}
    chunks = chunk_items([item])
    assert len(chunks) == 3 and all(len(c['summary']) <= 1200 for c in chunks)
    assert len({c['evidence_id'] for c in chunks}) == 3
    assert all(c['parent_evidence_id'] == 'project-a' and c['freelancer_id'] == 'alice' for c in chunks)
    assert chunk_items(chunks) == chunks


async def test_v0_uses_complete_job_once_and_mcp_routes_layers():
    calls = []
    async def search(query, k, filters):
        calls.append((query, k, filters))
        return []
    full_post = 'Celery project. ' * 300
    for variant, layer in [('v0_naive', 'dense'), ('v1_decomposed', 'dense'),
                           ('v2_hybrid', 'hybrid'), ('v3_rerank', 'rerank')]:
        cfg = load_config(overrides={'rag': {'variant': variant}})
        await build_retriever(cfg, [], search=search).retrieve(RetrievalQuery(full_post, [], {'freelancer_id': 'alice'}))
        assert calls[-1][0] == full_post and calls[-1][2]['retrieval_layer'] == layer
        assert calls[-1][2]['freelancer_id'] == 'alice'
    assert len(calls) == 4


def test_rrf_uses_ranks_and_merges_duplicate_items():
    result = rrf([[{'evidence_id': 'a', 'score': -100}, {'evidence_id': 'b', 'score': 100}],
                  [{'evidence_id': 'b', 'score': .001}]], 5)
    assert [r['evidence_id'] for r in result] == ['b', 'a']


async def test_langgraph_requeries_weak_evidence_then_accepts_and_preserves_filters():
    calls = []
    async def search(query, k, filters):
        calls.append(query)
        assert filters == {'freelancer_id': 'alice'}
        if 'Focus on missing' in query:
            return [{'evidence_id': 'celery', 'title': 'Celery Redis queues', 'summary': 'Celery retries', 'skills': []}]
        return []
    result = await retrieve_with_trace(RetrievalQuery('Build Celery queues', ['Celery', 'Redis'], {'freelancer_id': 'alice'}), search)
    assert result['accepted'] and result['attempts'] == 1
    assert [n['node'] for n in result['trace']] == ['retrieve', 'grade', 'requery', 'grade']
    assert len(calls) == 3 and result['coverage'] == 1


async def test_langgraph_refuses_after_one_correction_and_propagates_outages():
    async def irrelevant(query, k, filters):
        return [{'evidence_id': 'wrong', 'title': 'Baking', 'summary': 'Bread making', 'skills': []}]
    query = RetrievalQuery('Rust Kubernetes', ['Rust', 'Kubernetes'])
    result = await retrieve_with_trace(query, irrelevant)
    assert result['hits'] == [] and result['attempts'] == 1
    assert result['trace'][-1]['node'] == 'refuse'
    async def unavailable(query, k, filters):
        raise ConnectionError('fixture offline')
    with pytest.raises(ConnectionError):
        await retrieve_with_trace(query, unavailable)


async def test_mcp_honors_each_requested_layer_and_accepts_full_post():
    from mcp.shared.memory import create_connected_server_and_client_session as connect

    from mcp_servers.portfolio.server import build_server
    from mcp_servers.portfolio.tools import PortfolioStore
    store = PortfolioStore(freelancer_id='sample-ai-engineer')
    observed = []
    original = store._raw
    def instrument(query, filters, layer=None):
        observed.append((query, layer))
        return original(query, filters, layer)
    store._raw = instrument
    async with connect(build_server(store)) as session:
        for layer in ('dense', 'hybrid', 'rerank', 'hybrid_rerank'):
            result = await session.call_tool('search_evidence', {'requirement': 'scikit-learn classification ' * 100,
                'filters': {'freelancer_id': 'sample-ai-engineer', 'retrieval_layer': layer}, 'k': 5})
            assert not result.isError and result.structuredContent['items']
            assert observed[-1][1] == layer and len(observed[-1][0]) > 2000
