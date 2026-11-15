import json

from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.portfolio.server import build_server
from mcp_servers.portfolio.tools import PortfolioStore


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
