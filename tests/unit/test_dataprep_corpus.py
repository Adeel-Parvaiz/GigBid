import json

import pytest

from dataprep.build_corpus import build
from mcp_servers.marketplace.adapters.localsim import LocalSimAdapter
from mcp_servers.marketplace.adapters.sample import SampleAdapter

SMALL = {"n_hist": 120, "n_stream": 160, "n_dev": 30, "n_clients": 40}


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    d = tmp_path_factory.mktemp("corpus")
    m = build(d / "out", d / "dev", seed=3, **SMALL)
    return d, m


def load(d, name):
    return json.loads((d / "out" / name).read_text())


def test_build_is_deterministic_per_seed(corpus, tmp_path):
    d, m = corpus
    again = build(tmp_path / "o", tmp_path / "d", seed=3, **SMALL)
    other = build(tmp_path / "o2", tmp_path / "d2", seed=4, **SMALL)
    assert again["files"] == m["files"] and other["files"] != m["files"]


def test_rebuilding_same_output_does_not_hash_previous_manifest(tmp_path):
    out, dev = tmp_path / "out", tmp_path / "dev"
    first = build(out, dev, seed=2, **SMALL)
    second = build(out, dev, seed=2, **SMALL)
    assert second["files"] == first["files"]
    assert "DATA_MANIFEST.json" not in second["files"]


def test_everything_is_labelled_synthetic_or_real_and_sized_per_assignment(corpus):
    d, m = corpus
    jobs, items = load(d, "jobs.json"), load(d, "portfolio_items.json")
    assert all(j["provenance"] in {"real", "synthetic"} for j in jobs) and all(i["provenance"] == "synthetic" for i in items)
    for pid in ("ai-ml-engineer", "fullstack-dev", "data-analyst"):
        cs = [i for i in items if i["freelancer_id"] == pid and i["type"] == "case_study"]
        assert 15 <= len(cs) <= 25, pid                                   # assignment: 15-25 case studies per persona
        assert sum(1 for p in load(d, "past_proposals.json") if p["freelancer_id"] == pid) == 150
    assert {i["type"] for i in items} >= {"case_study", "readme", "review"}      # same project described several ways
    assert m["label_counts_stream"]["scam"] > 0 and m["label_counts_stream"]["duplicates"] > 0


def test_scams_and_injections_have_seeded_and_heldout_templates(corpus):
    d, _ = corpus
    flagged = [j for j in load(d, "jobs.json") if j["label"]["scam"] or j["label"]["injection"]]
    assert {j["label"]["template_set"] for j in flagged} == {"seeded", "heldout"}


def test_hidden_client_preferences_never_appear_in_agent_visible_data(corpus):
    d, _ = corpus
    hidden = load(d, "hidden_prefs.json")
    assert hidden and set(next(iter(hidden.values()))) == {"must_have", "budget_ceiling", "dislikes_generic"}
    visible = json.dumps([load(d, "jobs.json"), load(d, "clients.json"), load(d, "messages.json")])
    assert "must_have" not in visible and "budget_ceiling" not in visible and "dislikes_generic" not in visible


async def test_marketplace_agent_view_never_exposes_gold_labels(corpus):
    d, _ = corpus
    adapter = SampleAdapter(d / "out")
    jobs = await adapter.search_jobs(limit=10_000)
    assert jobs and all("label" not in job for job in jobs)
    assert "label" not in await adapter.get_job(jobs[0]["job_id"])


def test_dev_gold_is_consistent_with_its_own_rule_and_points_at_real_items(corpus):
    d, _ = corpus
    ids = {i["evidence_id"] for i in load(d, "portfolio_items.json")}
    corpus_job_ids = {j["job_id"] for j in load(d, "jobs.json")}
    for pid in ("ai-ml-engineer", "data-analyst"):
        rows = json.loads((d / "dev" / f"dev_{pid}.json").read_text())["jobs"]
        assert len(rows) == 30
        for r in rows:
            assert r["provenance"] == "synthetic" and r["label_provenance"] == "synthetic_rule"
            assert r["job_id"] in corpus_job_ids
            assert set(r["gold_evidence"]) <= ids
            if r["gold_action"] == "bid":
                assert not (r["scam"] or r["injection"]) and r["coverage"] >= 0.6


def test_real_jobs_are_merged_labelled_and_completed_synthetically(tmp_path):
    real = [{"job_id": f"real-{i}", "title": f"Python scikit-learn job {i}", "description": "Build a classification model with scikit-learn and pandas for our data. " * 2,
             "required_skills": ["Python", "scikit-learn", "pandas"], "budget": {"min": 500, "max": 500, "currency": "USD", "unit": "project"},
             "category": "ml_ai", "source_dataset": "fixture.csv", "provenance": "real", "synthetic_fields": ["client_id"]} for i in range(10)]
    m = build(tmp_path / "o", tmp_path / "d", real=real, seed=1, **SMALL)
    assert m["real_jobs_used"] == 10
    assert m["source_dataset_counts"]["fixture.csv"] == 10
    jobs = json.loads((tmp_path / "o" / "jobs.json").read_text())
    r = [j for j in jobs if j["provenance"] == "real" and not j.get("label", {}).get("duplicate_of")]
    assert r and all(j["client_id"].startswith("client-") and "client_id" in j["synthetic_fields"] for j in r)
    assert all("label" not in j for j in r)


async def test_local_simulator_rewards_what_it_says_it_rewards(corpus):
    d, _ = corpus
    sim, hidden = LocalSimAdapter(d / "out"), load(d, "hidden_prefs.json")
    jid = next(j for j, h in hidden.items() if h["must_have"] and h["dislikes_generic"] and h["budget_ceiling"] and j in sim._jobs and sim._jobs[j]["budget"]["unit"] == "project")
    job, h = sim._jobs[jid], hidden[jid]
    mk = lambda text, bid, key: sim.create_proposal_draft({"job_id": jid, "cover_letter": text, "screening_answers": [], "bid_amount": bid, "currency": "USD"}, key)  # noqa: E731
    good = f"For your {job['title']} I have delivered {', '.join(h['must_have'])} work before and can start now."
    await mk(good, h["budget_ceiling"] * 0.9, "k-good")
    await mk("I am writing to apply. I am the best freelancer and a perfect fit.", h["budget_ceiling"] * 0.9, "k-generic")
    await mk(good, h["budget_ceiling"] * 3, "k-pricey")
    p = {k: sim.reply_probability(k) for k in ("k-good", "k-generic", "k-pricey")}
    assert p["k-good"] > p["k-pricey"] and p["k-good"] > p["k-generic"] + 0.3
    assert sim.outcome_for("k-good") == sim.outcome_for("k-good")                # deterministic


async def test_hourly_jobs_are_priced_and_judged_per_hour(make_deps, profile):
    from langgraph.checkpoint.memory import InMemorySaver

    from agent.graphs.bid_graph import build_bid_graph
    deps = make_deps()
    base = deps.port._jobs["job-001"]
    deps.port._jobs["h-low"] = {**base, "job_id": "h-low", "budget": {"min": 10, "max": 15, "currency": "USD", "unit": "hour"}}
    deps.port._jobs["h-ok"] = {**base, "job_id": "h-ok", "budget": {"min": 20, "max": 60, "currency": "USD", "unit": "hour"}}
    g = build_bid_graph(deps, InMemorySaver())
    low = await g.ainvoke({"job_id": "h-low", "profile": profile}, {"configurable": {"thread_id": "h1"}})
    assert low["decision"].action == "skip" and "/h" in low["decision"].reasons[0]
    ok = await g.ainvoke({"job_id": "h-ok", "profile": profile}, {"configurable": {"thread_id": "h2"}})
    assert ok["decision"].action == "bid" and ok["price_quote"].amount == profile["hourly_rate_usd"] and "hourly" in ok["price_quote"].rationale
