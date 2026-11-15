"""Verify all B2 variants through official in-memory MCP using real neural backends."""
import asyncio
import json
import os
from pathlib import Path

from mcp.shared.memory import create_connected_server_and_client_session as connect

from agent.config import load_config
from mcp_servers.portfolio.server import build_server
from mcp_servers.portfolio.tools import PortfolioStore
from rag.retriever import RetrievalQuery, build_retriever
from rag.variants.v8_corrective import retrieve_with_trace

ROOT = Path(__file__).resolve().parents[2]


async def run():
    cfg = load_config(overrides={'rag': {'embedder': 'fastembed', 'reranker': 'fastembed',
                                        'cache_dir': str(ROOT / '.local-models/rag-cache')}})
    os.environ['PORTFOLIO_RAG_CONFIG'] = json.dumps(cfg['rag'])
    store = PortfolioStore(ROOT / 'data/sample', freelancer_id='sample-ai-engineer')
    calls, results = [], []
    async with connect(build_server(store)) as session:
        async def search(query, k, filters):
            result = await session.call_tool('search_evidence', {'requirement': query, 'k': k, 'filters': filters})
            assert not result.isError
            calls.append({'query': query, 'filters': filters, 'count': len(result.structuredContent['items'])})
            return result.structuredContent['items']
        query = RetrievalQuery('Build and evaluate a scikit-learn churn classification baseline.',
                               ['scikit-learn', 'classification'], {'freelancer_id': 'sample-ai-engineer'})
        for variant in ['v0_naive', 'v1_decomposed', 'v2_hybrid', 'v3_rerank', 'v8_corrective']:
            result = await build_retriever({**cfg, 'rag': {**cfg['rag'], 'variant': variant}}, [], search=search).retrieve(query)
            assert result and all(r['freelancer_id'] == 'sample-ai-engineer' for r in result)
            results.append({'variant': variant, 'ids': [r['evidence_id'] for r in result],
                            'last_requested_layer': calls[-1]['filters']['retrieval_layer']})
        refusal = await retrieve_with_trace(RetrievalQuery('Rust Kubernetes Kafka gRPC',
            ['Rust', 'Kubernetes', 'Kafka', 'gRPC'], {'freelancer_id': 'sample-ai-engineer', 'retrieval_layer': 'hybrid'}), search)
        assert refusal['hits'] == [] and refusal['trace'][-1]['node'] == 'refuse'
    assert type(store.reranker).__name__ == 'OnnxCrossEncoderReranker'
    output = {'scope': 'Actual official SDK MCP sessions; synthetic local sample evidence, real embedding and cross-encoder inference.',
              'variants': results, 'calls': calls, 'refusal_trace': refusal['trace'],
              'embedding': store.index.embedder.metadata, 'reranker': store.reranker.metadata}
    target = ROOT / 'evals/results/b2/mcp_verification.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2))
    print('Five variants and bounded refusal verified over MCP with real neural models')


if __name__ == '__main__':
    asyncio.run(run())
