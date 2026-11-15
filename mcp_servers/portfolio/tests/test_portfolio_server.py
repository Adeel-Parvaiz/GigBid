import json

import httpx
from cryptography.fernet import Fernet
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.memory import create_connected_server_and_client_session as connect

from apps.api.auth.oauth_store import OAuthVault
from mcp_servers.portfolio.identity import PortfolioIdentityMiddleware, portfolio_identity
from mcp_servers.portfolio.server import build_server
from mcp_servers.portfolio.tools import PortfolioStore
from rag.ingest.store import PortfolioCorpus


def payload(res):
    return res.structuredContent


async def test_lists_three_tools_with_read_only_annotations():
    async with connect(build_server()) as c:
        tools = (await c.list_tools()).tools
    assert {t.name for t in tools} == {"search_evidence", "get_case_study", "list_skills"}
    for t in tools:
        assert t.annotations.readOnlyHint is True and t.annotations.destructiveHint is False
        assert t.outputSchema is not None          # declared output schema


async def test_search_evidence_returns_typed_items_without_proposals_by_default():
    async with connect(build_server()) as c:
        r = await c.call_tool("search_evidence", {"requirement": "scikit-learn classification", "k": 3})
    items = payload(r)["items"]
    assert items and all(i["type"] == "case_study" for i in items)
    assert {"type", "source", "date", "outcome"} <= set(items[0])


async def test_past_proposals_only_when_asked_and_carry_outcome():
    async with connect(build_server()) as c:
        r = await c.call_tool("search_evidence", {"requirement": "proposal", "k": 5,
                                                  "filters": {"type": "past_proposal"}})
    items = payload(r)["items"]
    assert {i["outcome"] for i in items} == {"won", "ignored", "replied"}


async def test_input_validation_is_an_error_result_not_a_crash():
    async with connect(build_server()) as c:
        r = await c.call_tool("search_evidence", {"requirement": "x"})
        assert r.isError
        r = await c.call_tool("search_evidence", {"requirement": "python", "k": 99})
        assert r.isError
        r = await c.call_tool("get_case_study", {"id": "nope"})
        assert r.isError


async def test_resource_templates_and_prompts():
    async with connect(build_server()) as c:
        templates = {t.uriTemplate for t in (await c.list_resource_templates()).resourceTemplates}
        assert templates == {"portfolio://case/{case_id}", "portfolio://proposal/{proposal_id}"}
        case = json.loads((await c.read_resource("portfolio://case/evidence-001")).contents[0].text)
        assert case["title"] == "Customer churn classification"
        prop = json.loads((await c.read_resource("portfolio://proposal/prop-001")).contents[0].text)
        assert prop["outcome"] == "won"
        names = {p.name for p in (await c.list_prompts()).prompts}
        assert "answer_screening_question" in names
        got = await c.get_prompt("answer_screening_question", {"question": "Imbalanced data?"})
        assert "search_evidence" in got.messages[0].content.text


async def test_bound_server_refuses_another_freelancers_portfolio():
    server = build_server(PortfolioStore(freelancer_id="sample-ai-engineer"))
    async with connect(server) as c:
        r = await c.call_tool("search_evidence", {"requirement": "python", "filters": {"freelancer_id": "someone-else"}})
        assert r.isError and "bound" in r.content[0].text
        ok = await c.call_tool("list_skills", {})
        assert not ok.isError and payload(ok)["skills"]


async def test_server_side_retrieval_layers_return_ranked_typed_items():
    from mcp_servers.portfolio.tools import PortfolioStore
    for layer in ("dense", "hybrid", "hybrid_rerank"):
        async with connect(build_server(PortfolioStore(layer=layer))) as c:
            r = await c.call_tool("search_evidence", {"requirement": "Plotly Dash dashboard", "k": 2})
        assert payload(r)["items"][0]["evidence_id"] == "evidence-002", layer


async def test_http_identity_requires_internal_token_and_scopes_request_context():
    observed = []

    async def app(scope, receive, send):
        observed.append(portfolio_identity.get())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = PortfolioIdentityMiddleware(app, "internal-test-token")

    async def invoke(headers):
        sent = []

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "headers": headers}
        await middleware(scope, None, send)
        return sent

    unauthorized = await invoke([(b"x-gigbid-user-id", b"012345abcdef")])
    assert unauthorized[0]["status"] == 401
    assert observed == []

    authorized = await invoke([
        (b"authorization", b"Bearer internal-test-token"),
        (b"x-gigbid-user-id", b"012345abcdef"),
        (b"x-gigbid-freelancer-id", b"freelancer-1"),
    ])
    assert authorized[0]["status"] == 204
    assert observed == [("012345abcdef", "freelancer-1")]
    assert portfolio_identity.get() is None


async def test_http_mcp_reads_only_the_authenticated_users_imported_portfolio(tmp_path, monkeypatch):
    database = tmp_path / "oauth.sqlite"
    monkeypatch.setenv("OAUTH_DB", str(database))
    monkeypatch.setenv("OAUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("PORTFOLIO_INDEX_DB", str(tmp_path / "portfolio_index.sqlite"))
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8765")

    alice = "012345abcdef"
    bob = "abcdef012345"
    corpus = PortfolioCorpus(OAuthVault(database))
    ingested = corpus.ingest(
        alice,
        "sample-ai-engineer",
        "private-proof.md",
        b"uniqueprivateproofmarker verified private portfolio evidence",
        "case_study",
        {
            "title": "Private proof",
            "project": "Private portfolio",
            "skills": ["Python"],
            "date": "2026-01-01",
            "client_industry": "test",
            "outcome": None,
            "provenance": "synthetic",
            "authorship_confirmed": True,
        },
    )
    evidence_id = corpus.documents(alice)[0]["chunks"][0]["evidence_id"]

    server = build_server()
    app = server.streamable_http_app()
    app.add_middleware(PortfolioIdentityMiddleware, token="internal-test-token")

    async def search(user_id):
        headers = {
            "Authorization": "Bearer internal-test-token",
            "X-GigBid-User-ID": user_id,
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8765",
            headers=headers,
        ) as client:
            async with streamable_http_client("http://127.0.0.1:8765/mcp", http_client=client) as streams:
                async with ClientSession(*streams[:2]) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "search_evidence",
                        {"requirement": "uniqueprivateproofmarker", "k": 20},
                    )
                    assert not result.isError
                    return result.structuredContent["items"]

    async with app.router.lifespan_context(app):
        alice_items = await search(alice)
        bob_items = await search(bob)

    assert ingested["document_id"]
    assert any(item["evidence_id"] == evidence_id for item in alice_items)
    assert all(item["evidence_id"] != evidence_id for item in bob_items)
