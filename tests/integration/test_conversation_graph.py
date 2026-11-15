from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph, pending_approval
from agent.graphs.conversation_graph import build_conversation_graph
from agent.handoffs import IntentResult
from agent.llm import HeuristicLLM
from tests.conftest import cfg_of


async def start(g, thread, profile):
    return await g.ainvoke({"thread_id": thread, "profile": profile}, cfg_of(thread))


async def test_scam_message_is_flagged_nothing_drafted_or_sent(make_deps, profile):
    deps = make_deps()
    out = await start(build_conversation_graph(deps, InMemorySaver()), "conv-003", profile)
    assert out["status"] == "flagged" and out["intent"].intent == "scam_signal"
    assert {"scam_pattern", "prompt_injection"} <= set(out["intent"].flags)
    assert "reply" not in out and deps.port.sent == {}


async def test_token_budget_moves_conversation_to_needs_attention(make_deps, profile):
    deps = make_deps({"budgets": {"max_tokens_per_job": 1}})
    out = await start(build_conversation_graph(deps, InMemorySaver()), "conv-001", profile)
    assert out["status"] == "needs_attention"
    assert any("token budget 1" in error for error in out["errors"])


async def test_gullible_llm_cannot_downgrade_a_scam(make_deps, profile):
    class Gullible(HeuristicLLM):
        def _intent(self, i):
            return IntentResult(intent="question", rationale="looks fine")
    out = await start(build_conversation_graph(make_deps(llm=Gullible()), InMemorySaver()), "conv-003", profile)
    assert out["intent"].intent == "scam_signal"


async def test_question_reply_is_grounded_and_sent_once_after_approval(make_deps, profile):
    deps = make_deps()
    g = build_conversation_graph(deps, InMemorySaver())
    await start(g, "conv-001", profile)
    p = await pending_approval(g, cfg_of("conv-001"))
    assert p["kind"] == "message_approval" and p["intent"]["intent"] == "question"
    assert any(c["evidence_ids"] for c in p["draft"]["claims"]) and deps.port.sent == {}
    out = await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("conv-001"))
    assert out["status"] == "sent" and len(deps.port.sent) == 1
    again = await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("conv-001"))   # no pending interrupt -> no resend
    assert len(deps.port.sent) == 1 and again["status"] == "sent"


async def test_interview_request_offers_calendar_slots_and_holds_after_approval(make_deps, profile):
    deps = make_deps()
    g = build_conversation_graph(deps, InMemorySaver())
    await start(g, "conv-002", profile)
    p = await pending_approval(g, cfg_of("conv-002"))
    assert len(p["offered_slots"]) == 3 and p["offered_slots"][0] in p["draft"]["claims"][-1]["text"]
    assert deps.workspace.holds == {}                               # nothing held before approval
    out = await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("conv-002"))
    assert out["send_result"]["hold"]["status"] == "tentative" and len(deps.workspace.holds) == 1


async def test_edit_with_off_platform_contact_is_blocked(make_deps, profile):
    deps = make_deps()
    g = build_conversation_graph(deps, InMemorySaver())
    await start(g, "conv-001", profile)
    await g.ainvoke(Command(resume={"action": "edit", "edited_cover_letter": "Sure, add me on Telegram."}), cfg_of("conv-001"))
    p = await pending_approval(g, cfg_of("conv-001"))
    assert p["allowed_actions"] == ["edit", "reject"]
    await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("conv-001"))
    assert deps.port.sent == {}


async def test_message_edit_diff_is_shown_rechecked_and_saved_for_style_memory(make_deps, profile):
    class MemorySpy:
        def __init__(self):
            self.edits = []

        async def observe_edit(self, freelancer_id, job_id, original, edited):
            self.edits.append((freelancer_id, job_id, original, edited))
            return []

    deps = make_deps()
    deps.memory = MemorySpy()
    g = build_conversation_graph(deps, InMemorySaver())
    await start(g, "conv-001", profile)
    original = (await pending_approval(g, cfg_of("conv-001")))["draft"]["text"]
    parts = original.split(". ", 1)
    assert len(parts) == 2
    edited = parts[1]

    await g.ainvoke(Command(resume={"action": "edit", "edited_cover_letter": edited}), cfg_of("conv-001"))
    pending = await pending_approval(g, cfg_of("conv-001"))
    assert pending["edit_diff"] and pending["draft"]["text"] == edited
    assert pending["compliance_verdict"]["passed"]

    out = await g.ainvoke(Command(resume={"action": "approve"}), cfg_of("conv-001"))
    assert out["status"] == "sent" and out["edit_history"][0]["diff"]
    assert deps.memory.edits == [(profile["freelancer_id"], "job-001", original, edited)]


async def test_style_memory_learned_from_three_edited_jobs_changes_the_next_draft(make_deps, profile):
    deps = make_deps()
    g = build_bid_graph(deps, InMemorySaver())
    fid = profile["freelancer_id"]
    for n, job in enumerate(("job-001", "job-005", "job-004")):             # job-004 is skipped (injection): 2 usable edits
        await g.ainvoke({"job_id": job, "profile": profile}, cfg_of(f"s{n}"))
    # drive three edited submissions of the same job with different thread ids and job ids
    async def edited(job_id, tid):
        await g.ainvoke({"job_id": job_id, "profile": profile}, cfg_of(tid))
        p = await pending_approval(g, cfg_of(tid))
        letter = p["draft"]["cover_letter"]
        first = letter.split("\n\n")[0]
        await g.ainvoke(Command(resume={"action": "edit", "edited_cover_letter": letter.replace(first, "").strip()}), cfg_of(tid))
        return await g.ainvoke(Command(resume={"action": "approve"}), cfg_of(tid))
    deps.port.balance = 1000
    deps.port._jobs["job-006"] = {**deps.port._jobs["job-001"], "job_id": "job-006"}
    deps.port._jobs["job-007"] = {**deps.port._jobs["job-001"], "job_id": "job-007"}
    assert await deps.memory.style_rules(fid) == []
    for job_id in ("job-001", "job-006", "job-007"):
        await edited(job_id, f"edit-{job_id}")
    assert any("Do not open with" in r for r in await deps.memory.style_rules(fid))
    await g.ainvoke({"job_id": "job-005", "profile": profile}, cfg_of("after"))
    p = await pending_approval(g, cfg_of("after"))
    assert not any("close to work I have done" in c["text"] for c in p["draft"]["claims"])   # opener gone


async def test_llm_written_logistics_claim_is_discarded(make_deps, profile):
    from agent.handoffs import Claim, ReplyDraft
    class Sneaky(HeuristicLLM):
        def _liaison_reply(self, i):
            return ReplyDraft(thread_id=i["thread_id"], claims=[
                Claim(text="I have 12 years of experience at Google.", kind="logistics")])
    g = build_conversation_graph(make_deps(llm=Sneaky()), InMemorySaver())
    await start(g, "conv-002", profile)
    p = await pending_approval(g, cfg_of("conv-002"))
    assert "12 years" not in p["draft"]["text"] and p["offered_slots"]
