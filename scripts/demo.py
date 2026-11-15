"""python -m scripts.demo : walk jobs through the bid graph and stop at the human gate."""
import asyncio

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph, pending_approval
from agent.runtime import build_deps, load_sample_profile


async def main():
    deps, profile = build_deps(), load_sample_profile()
    g = build_bid_graph(deps, InMemorySaver())
    for jid in ("job-002", "job-003", "job-004", "job-001", "job-005"):
        cfg = {"configurable": {"thread_id": jid}}
        out = await g.ainvoke({"job_id": jid, "profile": profile}, cfg)
        fit = out["fit_report"]
        risk = out["risk_report"]
        decision = out["decision"]
        print(f"\n== {jid} {out['job']['title']}\n   risk={risk.score:.2f} {risk.flags}"
              f"\n   fit={fit.score:.2f} ({fit.variant}) missing={fit.missing_skills}"
              f"\n   decision={decision.action}: {decision.reasons}")
        if p := await pending_approval(g, cfg):
            print(f"   PAUSED for approval. price={p['price_quote']['amount']} connects={p['dry_run']['connects_cost']}")
            print("   claims:", [(c['text'][:40], c['evidence_ids']) for c in p['draft']['claims'] if c['kind'] == 'claim'])
            print("   cover letter:\n     " + p["draft"]["cover_letter"].replace("\n", "\n     "))
            if jid == "job-001":
                out = await g.ainvoke(Command(resume={"action": "approve"}), cfg)
                print("   -> approved:", out["submission"], "| connects left:", deps.port.balance)

asyncio.run(main())
