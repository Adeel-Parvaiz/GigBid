"""V8: a bounded LangGraph retrieval/grade/re-query/grade/accept-or-refuse loop.
The transparent grader measures lexical requirement coverage, not semantic entailment.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from rag.index.bm25 import tokenize
from rag.variants.v0_naive import RetrievalQuery, SearchFn
from rag.variants.v1_decomposed import retrieve as decomposed

GENERIC = {"python", "model", "data", "project", "build", "development", "engineer"}


def covers(hit: dict, requirement: str) -> bool:
    text = f"{hit.get('title', '')} {hit.get('summary', '')} {' '.join(hit.get('skills', []))}"
    terms = {t for t in tokenize(requirement) if t not in GENERIC and len(t) > 2}
    return bool(terms & set(tokenize(text))) or requirement.lower() in text.lower()


class RetrievalState(TypedDict, total=False):
    query: RetrievalQuery
    hits: list[dict]
    missing: list[str]
    coverage: float
    attempts: int
    accepted: bool
    trace: list[dict]


def build_graph(search: SearchFn, k=5, minimum_coverage=.5):
    if not 0 < minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be in (0, 1]")

    async def initial(state):
        hits = await decomposed(state["query"], search, k)
        return {"hits": hits, "attempts": 0, "trace": [{"node": "retrieve", "returned": len(hits)}]}

    def grade(state):
        reqs = state["query"].requirements or [state["query"].job_text]
        hits = [h for h in state["hits"] if any(covers(h, r) for r in reqs)]
        missing = [r for r in reqs if not any(covers(h, r) for h in hits)]
        coverage = 1 - len(missing) / len(reqs)
        accepted = bool(hits) and coverage >= minimum_coverage
        return {"hits": hits, "missing": missing, "coverage": coverage, "accepted": accepted,
                "trace": state["trace"] + [{"node": "grade", "coverage": coverage, "missing": missing, "accepted": accepted}]}

    async def correct(state):
        query = state["query"]
        rewritten = query.job_text + "\nFocus on missing evidence: " + "; ".join(state["missing"])
        hits = await search(rewritten, k, query.filters)
        return {"hits": hits, "attempts": state["attempts"] + 1,
                "trace": state["trace"] + [{"node": "requery", "query": rewritten, "returned": len(hits)}]}

    def refuse(state):
        return {"hits": [], "trace": state["trace"] + [{"node": "refuse", "reason": "Evidence coverage below threshold"}]}

    graph = StateGraph(RetrievalState)
    for name, function in [("retrieve", initial), ("grade", grade), ("requery", correct), ("refuse", refuse)]:
        graph.add_node(name, function)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", lambda s: "accept" if s["accepted"] else "requery" if s["attempts"] < 1 else "refuse",
                                {"accept": END, "requery": "requery", "refuse": "refuse"})
    graph.add_edge("requery", "grade")
    graph.add_edge("refuse", END)
    return graph.compile()


async def retrieve_with_trace(query: RetrievalQuery, search: SearchFn, k=5, minimum_coverage=.5):
    return await build_graph(search, k, minimum_coverage).ainvoke({"query": query}, {"recursion_limit": 10})


async def retrieve(query: RetrievalQuery, search: SearchFn, k=5, minimum_coverage=.5):
    return (await retrieve_with_trace(query, search, k, minimum_coverage))["hits"]
