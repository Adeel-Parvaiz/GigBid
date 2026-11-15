import json

from agent.config import load_config
from mcp_servers.marketplace.adapters.sample import DATA
from rag.index.bm25 import BM25Index
from rag.retriever import VARIANTS, RetrievalQuery, build_retriever

ITEMS = json.loads((DATA / "portfolio_items.json").read_text())
FID = {"freelancer_id": "sample-ai-engineer"}


def retr(name):
    return build_retriever({**load_config(), "rag": {**load_config()["rag"], "variant": name}}, ITEMS)


def test_bm25_nails_exact_tool_names():
    top = BM25Index(ITEMS).search("Plotly Dash", 3)
    assert top[0]["evidence_id"] == "evidence-002"
    assert BM25Index(ITEMS).search("Kubernetes", 3) == []          # absent term: no spurious match


async def test_every_variant_runs_and_respects_tenant_filter():
    q = RetrievalQuery("fraud classifier with imbalance and a dashboard",
                       ["scikit-learn", "imbalanced learning", "dashboarding"], FID)
    for name in VARIANTS:
        hits = await retr(name).retrieve(q, 3)
        assert all(h["freelancer_id"] == "sample-ai-engineer" for h in hits), name
    other = RetrievalQuery(q.job_text, q.requirements, {"freelancer_id": "nobody"})
    for name in VARIANTS:
        assert await retr(name).retrieve(other, 3) == [], name


async def test_rerank_puts_the_lexically_best_item_first():
    q = RetrievalQuery("imbalanced learning SMOTE PR-AUC", [], FID)
    assert (await retr("v3_rerank").retrieve(q, 3))[0]["evidence_id"] == "evidence-004"


async def test_corrective_refuses_to_claim_when_nothing_relevant():
    rust = RetrievalQuery("Rust Kubernetes gRPC Kafka recommender", ["Rust", "Kubernetes", "gRPC", "Kafka"], FID)
    assert await retr("v8_corrective").retrieve(rust, 5) == []                 # refuse: no evidence to cite
    assert await retr("v1_decomposed").retrieve(rust, 5) != []                 # naive variants return irrelevant filler
    ok = RetrievalQuery("churn model", ["scikit-learn", "classification"], FID)
    assert {h["evidence_id"] for h in await retr("v8_corrective").retrieve(ok, 5)} >= {"evidence-001"}
