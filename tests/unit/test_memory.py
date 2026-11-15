from agent.memory.promotion_rules import extract_signals
from agent.memory.store import MemoryManager

ORIG = "I am passionate about data. I built a churn model. I compared two classifiers."
EDIT = "I built a churn model. I compared two classifiers."


def test_signals_ignore_full_rewrites():
    assert "cut_first_sentence" in extract_signals(ORIG, EDIT)
    assert extract_signals(ORIG, "Totally different text. Nothing shared at all.") == []


async def test_one_edit_is_not_enough_three_distinct_jobs_promote():
    m = MemoryManager(promote_after=3)
    assert await m.observe_edit("f", "job-1", ORIG, EDIT) == [] and await m.style_rules("f") == []
    assert await m.observe_edit("f", "job-1", ORIG, EDIT) == []  # same job again does not count
    assert await m.observe_edit("f", "job-2", ORIG, EDIT) == []
    assert "cut_first_sentence" in await m.observe_edit("f", "job-3", ORIG, EDIT)
    rules = await m.list_style("f")
    assert any(r["id"] == "cut_first_sentence" and r["learned_from_jobs"] == ["job-1", "job-2", "job-3"] for r in rules)


async def test_user_delete_removes_rule_and_resets_progress():
    m = MemoryManager(promote_after=2)
    for j in ("a", "b"):
        await m.observe_edit("f", j, ORIG, EDIT)

    async def ids():
        return {r["id"] for r in await m.list_style("f")}

    assert "cut_first_sentence" in await ids() and "avoid_word:passionate" in await ids()
    await m.delete_style("f", "cut_first_sentence")
    assert "cut_first_sentence" not in await ids() and "avoid_word:passionate" in await ids()
    await m.observe_edit("f", "c", ORIG, EDIT)  # one new edit must not re-promote
    assert "cut_first_sentence" not in await ids()


async def test_memory_is_per_freelancer():
    m = MemoryManager(promote_after=1)
    await m.observe_edit("alice", "j", ORIG, EDIT)
    assert await m.style_rules("alice") and await m.style_rules("bob") == []


async def test_outcome_memory_hidden_until_enough_samples_and_dedupes_runs():
    m = MemoryManager(min_outcomes=5)
    for run_id, outcome in (
        ("run-1", "won"),
        ("run-2", "replied"),
        ("run-3", "ignored"),
        ("run-4", "ignored"),
    ):
        await m.record_outcome("f", "ml", outcome, event_id=run_id)
    await m.record_outcome("f", "ml", "won", event_id="run-1")  # retry must not add another result
    assert await m.outcome_memory("f") == {}
    await m.record_outcome("f", "ml", "ignored", event_id="run-5")
    assert (await m.outcome_memory("f"))["ml"] == {"n": 5, "reply_rate": 0.4, "win_rate": 0.2}
    await m.record_outcome("f", "ml", "ignored", event_id="run-1")  # an update replaces the same run
    assert (await m.outcome_memory("f"))["ml"] == {"n": 5, "reply_rate": 0.2, "win_rate": 0.0}
    await m.delete_outcome("f", "ml")
    assert await m.outcome_memory("f") == {}
