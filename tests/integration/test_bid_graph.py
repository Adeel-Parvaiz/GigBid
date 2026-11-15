from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph, pending_approval
from agent.handoffs import ApprovalDecision, BidDecision, Critique, ProposalDraft
from agent.llm import HeuristicLLM
from tests.conftest import cfg_of


async def run(graph, job_id, profile, thread):
    return await graph.ainvoke({"job_id": job_id, "profile": profile}, cfg_of(thread))


async def test_scam_is_skipped_and_nothing_is_sent(make_deps, profile):
    deps = make_deps()
    g = build_bid_graph(deps, InMemorySaver())
    out = await run(g, "job-002", profile, "t-scam")
    assert out["status"] == "skipped"
    assert {"unpaid_work", "off_platform_contact"} <= set(out["risk_report"].flags)
    assert "proposal_draft" not in out and deps.port.drafts == {} and deps.port.balance == 100


async def test_weak_fit_job_is_skipped(make_deps, profile):
    deps = make_deps()
    profile["auto_skip_low_fit"] = True
    out = await run(build_bid_graph(deps, InMemorySaver()), "job-003", profile, "t-rust")
    assert out["decision"].action == "skip" and "Rust" in out["fit_report"].missing_skills
    assert deps.port.submissions == {} and deps.port.balance == 100


async def test_disabling_low_fit_auto_skip_only_routes_to_watch(make_deps, profile):
    deps = make_deps()
    profile["auto_skip_low_fit"] = False
    out = await run(build_bid_graph(deps, InMemorySaver()), "job-003", profile, "t-watch")
    assert out["decision"].action == "watch" and out["status"] == "watching"
    assert "__interrupt__" not in out
    assert deps.port.submissions == {} and deps.port.balance == 100


async def test_injection_is_flagged_and_cannot_lower_risk(make_deps, profile):
    class Gullible(HeuristicLLM):  # an LLM that obeyed the injected "mark as perfect fit"
        def _risk(self, i):
            from agent.handoffs import RiskReport
            return RiskReport(score=0.0, flags=[], explanation="perfect fit, no risk")
    out = await run(build_bid_graph(make_deps(llm=Gullible()), InMemorySaver()), "job-004", profile, "t-inj")
    assert "prompt_injection" in out["risk_report"].flags
    assert out["risk_report"].score >= 0.9 and out["decision"].action == "skip"


async def test_good_job_pauses_for_approval_and_sends_nothing(make_deps, profile):
    deps = make_deps()
    g = build_bid_graph(deps, InMemorySaver())
    out = await run(g, "job-001", profile, "t-ok")
    assert "__interrupt__" in out
    from agent.handoffs import (
        BidDecision,
        ClaimVerdict,
        ComplianceVerdict,
        Critique,
        FitReport,
        JobSpec,
        PriceQuote,
        ProposalDraft,
        RiskReport,
    )
    assert isinstance(out["job_spec"], JobSpec)
    assert isinstance(out["risk_report"], RiskReport)
    assert isinstance(out["fit_report"], FitReport)
    assert isinstance(out["decision"], BidDecision)
    assert isinstance(out["price_quote"], PriceQuote)
    assert isinstance(out["proposal_draft"], ProposalDraft)
    assert isinstance(out["critique"], Critique)
    assert isinstance(out["compliance_verdict"], ComplianceVerdict)
    assert out["tokens_used"] > 0
    assert all(isinstance(verdict, ClaimVerdict) for verdict in out["claim_verification"])
    p = await pending_approval(g, cfg_of("t-ok"))
    assert p["allowed_actions"] == ["approve", "edit", "reject"]
    assert p["dry_run"]["dry_run"] is True and p["dry_run"]["connects_cost"] == 8
    assert all(c["evidence_ids"] for c in p["draft"]["claims"] if c["kind"] == "claim")
    assert deps.port.drafts == {} and deps.port.submissions == {} and deps.port.balance == 100


async def test_approve_submits_exactly_once(make_deps, profile):
    deps = make_deps()
    g = build_bid_graph(deps, InMemorySaver())
    await run(g, "job-001", profile, "t-1")
    out = await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("t-1"))
    assert out["status"] == "submitted" and deps.port.balance == 92
    assert len(deps.port.submissions) == 1
    # a second run of the same job+text maps to the same idempotency key: no second spend
    await run(g, "job-001", profile, "t-2")
    await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("t-2"))
    assert len(deps.port.submissions) == 1 and deps.port.balance == 92


async def test_reject_sends_nothing(make_deps, profile):
    deps = make_deps()
    g = build_bid_graph(deps, InMemorySaver())
    await run(g, "job-001", profile, "t-rej")
    out = await g.ainvoke(Command(resume={"action": "reject", "reason": "too generic"}), cfg_of("t-rej"))
    assert out["status"] == "rejected" and deps.port.submissions == {}


async def test_edit_is_rechecked_by_compliance_and_blocks_approve(make_deps, profile):
    deps = make_deps()
    g = build_bid_graph(deps, InMemorySaver())
    await run(g, "job-001", profile, "t-edit")
    bad = "Happy to help. WhatsApp me on +92 300 1234567 and I guarantee results."
    await g.ainvoke(Command(resume={"action": "edit", "edited_cover_letter": bad}), cfg_of("t-edit"))
    p = await pending_approval(g, cfg_of("t-edit"))
    assert p["allowed_actions"] == ["edit", "reject"] and p["blocking_reasons"]
    assert p["edit_diff"]
    assert "92 300" not in p["draft"]["cover_letter"] and "guarantee" not in p["draft"]["cover_letter"].lower()
    # approving while blocked is refused server-side and the thread stays paused
    await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("t-edit"))
    assert deps.port.submissions == {} and await pending_approval(g, cfg_of("t-edit"))
    # a clean edit unblocks it, then approve works
    await g.ainvoke(Command(resume={"action": "edit", "edited_cover_letter": "Happy to scope this here."}), cfg_of("t-edit"))
    out = await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("t-edit"))
    assert out["status"] == "submitted" and len(out["edit_history"]) == 2


async def test_critic_loop_is_bounded_at_two_revisions(make_deps, profile):
    class StrictCritic(HeuristicLLM):
        def _critic(self, i):
            return Critique(passed=False, score=0.2, issues=["always unhappy"])
    deps = make_deps(llm=StrictCritic())
    g = build_bid_graph(deps, InMemorySaver())
    out = await run(g, "job-001", profile, "t-loop")
    assert out["revisions"] == 2 and out["critique"].passed is False
    assert sum(1 for t in out["trace"] if t["node"] == "writer") == 3
    assert "__interrupt__" in out  # still reaches the human, with the failing critique visible


async def test_step_budget_moves_thread_to_needs_attention(make_deps, profile):
    deps = make_deps({"budgets": {"max_graph_steps": 3}})
    out = await run(build_bid_graph(deps, InMemorySaver()), "job-001", profile, "t-budget")
    assert out["status"] == "needs_attention"


async def test_token_budget_moves_bid_thread_to_needs_attention(make_deps, profile):
    deps = make_deps({"budgets": {"max_tokens_per_job": 1}})
    out = await run(build_bid_graph(deps, InMemorySaver()), "job-001", profile, "t-token-budget")
    assert out["status"] == "needs_attention"
    assert any("token budget 1" in error for error in out["errors"])


async def test_missing_job_is_a_clean_error(make_deps, profile):
    out = await run(build_bid_graph(make_deps(), InMemorySaver()), "nope", profile, "t-404")
    assert out["status"] == "error"


async def test_crash_and_resume_submits_once(make_deps, profile, tmp_path):
    db, deps = str(tmp_path / "ckpt.sqlite"), make_deps()
    async with AsyncSqliteSaver.from_conn_string(db) as saver:           # process 1: run to the gate
        paused = await run(build_bid_graph(deps, saver), "job-001", profile, "t-crash")
        tokens_at_pause = paused["tokens_used"]
    async with AsyncSqliteSaver.from_conn_string(db) as saver:           # "restart": new graph, same DB
        g2 = build_bid_graph(deps, saver)
        assert await pending_approval(g2, cfg_of("t-crash"))             # approval survived
        out = await g2.ainvoke(Command(resume={"action": "approve"}), cfg_of("t-crash"))
    assert isinstance(out["decision"], BidDecision)
    assert isinstance(out["proposal_draft"], ProposalDraft)
    assert isinstance(out["approval"], ApprovalDecision)
    assert out["tokens_used"] == tokens_at_pause
    assert out["status"] == "submitted" and len(deps.port.submissions) == 1 and deps.port.balance == 92


async def test_policy_change_is_a_config_edit_only(make_deps, profile):
    """Change-request drill: a new rule lands via config; no code changes."""
    rule = {"id": "no_discount", "pattern": r"(?i)\bdiscount\b", "action": "block"}
    base = make_deps().cfg["compliance"]["rules"]
    deps = make_deps({"compliance": {"rules": base + [rule]}})
    g = build_bid_graph(deps, InMemorySaver())
    await run(g, "job-001", profile, "t-cfg")
    await g.ainvoke(Command(resume={"action": "edit", "edited_cover_letter": "Special discount for you."}), cfg_of("t-cfg"))
    p = await pending_approval(g, cfg_of("t-cfg"))
    assert any("no_discount" in r for r in p["blocking_reasons"])
