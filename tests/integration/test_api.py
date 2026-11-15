import asyncio
import json

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent.marketplace_mcp import McpMarketplacePort
from agent.mcp_client import AgentTools
from apps.api.main import create_app
from apps.api.runs import RunStore


def client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def login(c, email="reviewer@gigbid.test", pw="reviewer-pass-1"):
    r = await c.post("/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def events(c, h, run_id, after=0):
    out = []
    async with c.stream("GET", f"/runs/{run_id}/events", params={"after": after}, headers=h) as r:
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out


async def wait_status(c, h, run_id, want, timeout=8):
    for _ in range(int(timeout / 0.05)):
        s = (await c.get(f"/runs/{run_id}", headers=h)).json()["status"]
        if s in want:
            return s
        await asyncio.sleep(0.05)
    raise AssertionError(f"status stuck at {s}")


@pytest.fixture
def app(make_deps):
    return create_app(deps=make_deps(), checkpointer=InMemorySaver())


async def test_auth_required_and_register_login(app):
    async with client(app) as c:
        assert (await c.get("/jobs")).status_code == 401
        assert (await c.post("/auth/login", json={"email": "reviewer@gigbid.test", "password": "wrong-pass-1"})).status_code == 401
        r = await c.post("/auth/register", json={"email": "new@x.io", "password": "longenough1"})
        assert r.status_code == 200 and r.json()["user"]["freelancer_id"] == "sample-ai-engineer"
        assert (await c.post("/auth/register", json={"email": "new@x.io", "password": "longenough1"})).status_code == 409


async def test_inbox_to_streamed_run_to_approved_submission(app):
    async with client(app) as c:
        h = await login(c)
        run = (await c.post("/jobs/job-001/runs", headers=h)).json()
        evs = await events(c, h, run["run_id"])
        nodes = [e["node"] for e in evs if e["type"] == "node"]
        assert {"analyst", "risk", "fit_matcher"} <= set(nodes) and nodes.index("decide") > nodes.index("fit_matcher")
        assert evs[-1]["type"] == "interrupt" and "approve" in evs[-1]["payload"]["allowed_actions"]
        pend = (await c.get("/approvals/pending", headers=h)).json()           # what a page refresh calls
        assert [p["run"]["run_id"] for p in pend] == [run["run_id"]]
        detail = (await c.get(f"/runs/{run['run_id']}", headers=h)).json()
        cover_claim = next(
            i for i, claim in enumerate(detail["pending"]["draft"]["claims"])
            if claim["section"] == "cover" and claim["kind"] == "claim" and claim["evidence_ids"]
        )
        regenerated = await c.post(
            f"/runs/{run['run_id']}/regenerate-paragraph",
            json={"claim_index": cover_claim},
            headers=h,
        )
        assert regenerated.status_code == 200 and regenerated.json()["text"], regenerated.text
        assert (await c.post(f"/runs/{run['run_id']}/approval", json={"action": "approve"}, headers=h)).status_code == 202
        after = await events(c, h, run["run_id"], after=evs[-1]["seq"])
        assert after[-1] == {**after[-1], "type": "done", "status": "submitted"}
        assert (await c.get("/approvals/pending", headers=h)).json() == []
        a = (await c.get("/analytics", headers=h)).json()
        assert a["connects_spent"] == 8 and a["by_status"] == {"submitted": 1} and a["latency_ms_p50"] is not None
        assert a["jobs_analyzed"] == a["proposals"] == 1
        assert a["average_tokens_per_job"] > 0 and a["average_tokens_per_proposal"] > 0
        assert a["run_metrics"][0]["trace_id"] == run["trace_id"]
        assert a["run_metrics"][0]["cost_usd"] is None and a["billing"] == "test_backend"
        assert a["run_metrics"][0]["output_tokens_per_second"] is None
        pipe = (await c.get("/pipeline", headers=h)).json()["columns"]
        assert [r["run_id"] for r in pipe["submitted"]] == [run["run_id"]]
        jobs = (await c.get("/jobs", headers=h)).json()
        assert jobs[0]["job_id"] == "job-001" and jobs[0]["recommended_action"] == "bid" and jobs[0]["price"]
        assert "Compare logistic regression and random forest" in jobs[0]["description"]


async def test_checkpoint_history_replays_selected_node(app):
    async with client(app) as c:
        h = await login(c)
        run = (await c.post("/jobs/job-001/runs", headers=h)).json()
        await events(c, h, run["run_id"])
        history = (await c.get(f"/runs/{run['run_id']}/history", headers=h)).json()
        assert len(history["items"]) > 5 and "writer" in history["available_nodes"]
        checkpoint = next(item for item in history["items"] if "writer" in item["next"])

        response = await c.post(
            f"/runs/{run['run_id']}/replay",
            json={"checkpoint_id": checkpoint["checkpoint_id"], "node": "writer"},
            headers=h,
        )
        assert response.status_code == 202
        replay_events = await events(c, h, run["run_id"])
        assert replay_events[-1]["type"] == "interrupt"
        detail = (await c.get(f"/runs/{run['run_id']}", headers=h)).json()
        assert detail["status"] == "awaiting_approval" and detail["pending"] is not None
        assert detail["summary"]["submission"] is None


async def test_scam_job_is_skipped_via_api(app):
    async with client(app) as c:
        h = await login(c)
        run = (await c.post("/jobs/job-002/runs", headers=h)).json()
        evs = await events(c, h, run["run_id"])
        assert evs[-1]["type"] == "done" and evs[-1]["status"] == "skipped"
        d = (await c.get(f"/runs/{run['run_id']}", headers=h)).json()
        assert "unpaid_work" in d["summary"]["risk_report"]["flags"] and d["pending"] is None


async def test_token_budget_reason_and_usage_are_visible_in_run_detail(make_deps):
    app = create_app(deps=make_deps({"budgets": {"max_tokens_per_job": 1}}),
                     checkpointer=InMemorySaver())
    async with client(app) as c:
        h = await login(c)
        run = (await c.post("/jobs/job-001/runs", headers=h)).json()
        await events(c, h, run["run_id"])
        detail = (await c.get(f"/runs/{run['run_id']}", headers=h)).json()
        assert detail["status"] == "needs_attention"
        assert any("token budget 1" in error for error in detail["summary"]["errors"])
        assert detail["summary"]["tokens_used"] == 0


async def test_repeated_job_start_reuses_run_and_model_failure_is_terminal(make_deps):
    app = create_app(deps=make_deps(), checkpointer=InMemorySaver())
    async with client(app) as c:
        h = await login(c)
        rid = (await c.post("/jobs/job-001/runs", headers=h)).json()["run_id"]
        assert (await c.post("/jobs/job-001/runs", headers=h)).json()["run_id"] == rid
        await events(c, h, rid)
        assert (await c.post("/jobs/job-001/runs", headers=h)).json()["run_id"] == rid

    class FailingModel:
        async def structured(self, *args):
            raise ConnectionError("model endpoint unavailable")

    failed = create_app(deps=make_deps(llm=FailingModel()), checkpointer=InMemorySaver())
    async with client(failed) as c:
        h = await login(c)
        rid = (await c.post("/jobs/job-001/runs", headers=h)).json()["run_id"]
        ev = await events(c, h, rid)
        assert ev[-1]["status"] == "dead_letter"
        detail = (await c.get(f"/runs/{rid}", headers=h)).json()
        assert detail["status"] == "dead_letter" and "ConnectionError" in detail["summary"]["failure_reason"]
        letters = (await c.get("/runs/dead-letters", headers=h)).json()
        assert [item["run_id"] for item in letters] == [rid]


async def test_per_node_timeout_retries_before_dead_letter(make_deps):
    import asyncio

    from agent.llm import HeuristicLLM

    calls = []

    class SlowAnalyst(HeuristicLLM):
        async def structured(self, node, schema, inputs):
            if node == "analyst":
                calls.append(node)
                await asyncio.sleep(0.1)
            return await super().structured(node, schema, inputs)

    deps = make_deps(
        {"resilience": {"nodes": {"analyst": {"timeout_seconds": 0.01, "max_attempts": 2}}}},
        llm=SlowAnalyst(),
    )
    app = create_app(deps=deps, checkpointer=InMemorySaver())
    async with client(app) as c:
        h = await login(c)
        rid = (await c.post("/jobs/job-001/runs", headers=h)).json()["run_id"]
        ev = await events(c, h, rid)
        assert ev[-1]["status"] == "dead_letter"
        assert calls == ["analyst", "analyst"]


async def test_uncertain_failure_after_approval_needs_attention_not_dead_letter(make_deps):
    deps = make_deps()

    async def uncertain_submit(draft_id, idempotency_key):
        raise ConnectionError("submission response lost")

    deps.port.submit_proposal = uncertain_submit
    app = create_app(deps=deps, checkpointer=InMemorySaver())
    async with client(app) as c:
        h = await login(c)
        rid = (await c.post("/jobs/job-001/runs", headers=h)).json()["run_id"]
        ev = await events(c, h, rid)
        await c.post(f"/runs/{rid}/approval", json={"action": "approve"}, headers=h)
        resumed = await events(c, h, rid, after=ev[-1]["seq"])
        assert resumed[-1]["type"] == "done" and resumed[-1]["status"] == "needs_attention"
        detail = (await c.get(f"/runs/{rid}", headers=h)).json()
        assert detail["status"] == "needs_attention"
        assert (await c.get("/runs/dead-letters", headers=h)).json() == []


async def test_other_users_cannot_see_or_approve_my_runs(app):
    async with client(app) as c:
        a = await login(c)
        run = (await c.post("/jobs/job-001/runs", headers=a)).json()
        await events(c, a, run["run_id"])
        b = {"Authorization": "Bearer " + (await c.post("/auth/register", json={"email": "bob@x.io", "password": "longenough1"})).json()["token"]}
        rid = run["run_id"]
        assert (await c.get(f"/runs/{rid}", headers=b)).status_code == 404
        assert (await c.get(f"/runs/{rid}/history", headers=b)).status_code == 404
        assert (await c.post(f"/runs/{rid}/replay", json={"checkpoint_id": "other", "node": "writer"}, headers=b)).status_code == 404
        assert (await c.post(f"/runs/{rid}/approval", json={"action": "approve"}, headers=b)).status_code == 404
        assert (await c.get(f"/runs/{rid}/events", headers=b)).status_code == 404
        assert (await c.get("/approvals/pending", headers=b)).json() == [] and (await c.get("/runs", headers=b)).json() == []


async def test_blocked_draft_cannot_be_approved_via_api_and_reject_records_reason(app):
    async with client(app) as c:
        h = await login(c)
        run = (await c.post("/jobs/job-001/runs", headers=h)).json()
        rid = run["run_id"]
        ev = await events(c, h, rid)
        assert (await c.post(f"/runs/{rid}/approval", json={"action": "edit"}, headers=h)).status_code == 422
        assert (await c.post(f"/runs/{rid}/approval", json={"action": "reject"}, headers=h)).status_code == 422
        await c.post(f"/runs/{rid}/approval", json={"action": "edit", "edited_cover_letter": "Text me on WhatsApp"}, headers=h)
        ev = await events(c, h, rid, after=ev[-1]["seq"])
        assert ev[-1]["type"] == "interrupt" and ev[-1]["payload"]["allowed_actions"] == ["edit", "reject"]
        assert (await c.post(f"/runs/{rid}/approval", json={"action": "approve"}, headers=h)).status_code == 409
        await c.post(f"/runs/{rid}/approval", json={"action": "reject", "reason": "contact request"}, headers=h)
        assert await wait_status(c, h, rid, {"rejected"}) == "rejected"
        assert (await c.get("/analytics", headers=h)).json()["top_rejection_reasons"] == [["contact request", 1]]
        assert (await c.post(f"/runs/{rid}/approval", json={"action": "approve"}, headers=h)).status_code == 409   # nothing pending


async def test_pending_approval_survives_api_restart_and_submits_once(make_deps, tmp_path):
    deps, ckpt, runs_db = make_deps(), str(tmp_path / "c.sqlite"), str(tmp_path / "r.sqlite")
    async with AsyncSqliteSaver.from_conn_string(ckpt) as cp:
        app1 = create_app(deps=deps, checkpointer=cp, run_store=RunStore(runs_db))
        async with client(app1) as c:
            h = await login(c)
            rid = (await c.post("/jobs/job-001/runs", headers=h)).json()["run_id"]
            await events(c, h, rid)
    # --- API process "killed"; a new one starts on the same databases ---
    from apps.api.auth.users import UserStore
    async with AsyncSqliteSaver.from_conn_string(ckpt) as cp:
        app2 = create_app(deps=deps, checkpointer=cp, run_store=RunStore(runs_db), seed=False)
        app2.state.users = app1.state.users
        async with client(app2) as c:
            h = await login(c)
            assert [p["run"]["run_id"] for p in (await c.get("/approvals/pending", headers=h)).json()] == [rid]
            ev = await events(c, h, rid)                                          # synthesized from the checkpoint
            assert ev[-1]["type"] == "interrupt"
            await c.post(f"/runs/{rid}/approval", json={"action": "approve"}, headers=h)
            assert await wait_status(c, h, rid, {"submitted"}) == "submitted"
    assert len(deps.port.submissions) == 1 and deps.port.balance == 92
    _ = UserStore


async def test_marketplace_down_degrades_queues_and_recovers(make_deps):
    from mcp_servers.marketplace.adapters.sample import SampleAdapter
    dead = McpMarketplacePort(AgentTools({"m": {"transport": "streamable_http", "url": "http://127.0.0.1:9/mcp"}}, timeout=2, retries=0))
    deps = make_deps(port=dead)
    app = create_app(deps=deps, checkpointer=InMemorySaver())
    async with client(app) as c:
        h = await login(c)
        assert (await c.get("/health")).json()["marketplace"] == "degraded"
        assert (await c.get("/jobs", headers=h)).status_code == 503                       # UI shows "marketplace unavailable"
        rid = (await c.post("/jobs/job-001/runs", headers=h)).json()["run_id"]
        assert await wait_status(c, h, rid, {"queued_degraded"}) == "queued_degraded"
        assert (await c.get("/health")).json()["queued_degraded_runs"] == 1
        deps.port = SampleAdapter()                                                       # marketplace comes back
        assert (await c.get("/health")).json()["marketplace"] == "ok"
        assert (await c.post("/admin/retry-degraded", headers=h)).json() == {"retried": 1}
        runs = (await c.get("/runs", headers=h)).json()
        assert {r["status"] for r in runs} <= {"superseded", "running", "awaiting_approval"}
        new = next(r for r in runs if r["status"] != "superseded")
        assert await wait_status(c, h, new["run_id"], {"awaiting_approval"}) == "awaiting_approval"
        assert (await c.get("/health")).json()["queued_degraded_runs"] == 0


async def test_conversation_flow_and_memory_viewer(app):
    async with client(app) as c:
        h = await login(c)
        threads = (await c.get("/conversations", headers=h)).json()
        assert {t["thread_id"] for t in threads} == {"conv-001", "conv-002", "conv-003"}
        run = (await c.post("/conversations/conv-002/runs", headers=h)).json()
        ev = await events(c, h, run["run_id"])
        assert ev[-1]["type"] == "interrupt" and ev[-1]["payload"]["kind"] == "message_approval" and ev[-1]["payload"]["offered_slots"]
        scam = (await c.post("/conversations/conv-003/runs", headers=h)).json()
        assert (await events(c, h, scam["run_id"]))[-1]["status"] == "flagged"
        mem = (await c.get("/memory", headers=h)).json()
        assert mem == {"style": [], "outcome": {}}
        assert (await c.delete("/memory/style/nope", headers=h)).status_code == 204
        assert (await c.delete("/memory/outcome/ml", headers=h)).status_code == 204


async def test_outcome_events_move_cards_and_feed_memory(app):
    async with client(app) as c:
        h = await login(c)
        rid = (await c.post("/jobs/job-001/runs", headers=h)).json()["run_id"]
        await events(c, h, rid)
        assert (await c.post(f"/runs/{rid}/outcome", json={"outcome": "replied"}, headers=h)).status_code == 404   # not submitted yet
        await c.post(f"/runs/{rid}/approval", json={"action": "approve"}, headers=h)
        await wait_status(c, h, rid, {"submitted"})
        assert (await c.post(f"/runs/{rid}/outcome", json={"outcome": "replied"}, headers=h)).status_code == 204
        cols = (await c.get("/pipeline", headers=h)).json()["columns"]
        assert [r["run_id"] for r in cols["replied"]] == [rid] and cols["submitted"] == []
        assert (await c.get("/memory", headers=h)).json()["outcome"] == {}                  # 1 sample < min_outcomes: hidden
        run = app.state.manager.store.get(rid)
        job = (await app.state.manager.values(run)).get("job", {})
        category = (job.get("required_skills") or ["general"])[0]
        assert (await c.delete(f"/memory/outcome/{category}", headers=h)).status_code == 204


async def test_openapi_schema_exposes_typed_models(app):
    async with client(app) as c:
        spec = (await c.get("/openapi.json")).json()
    assert {"RunDetail", "JobCard", "ApprovalDecision", "AnalyticsOut"} <= set(spec["components"]["schemas"])


async def test_settings_apply_to_next_run_and_retry_is_scoped_to_owner(make_deps):
    from mcp_servers.marketplace.adapters.sample import SampleAdapter
    dead = McpMarketplacePort(AgentTools({"m": {"transport": "streamable_http", "url": "http://127.0.0.1:9/mcp"}}, timeout=2, retries=0))
    deps = make_deps(port=dead)
    app = create_app(deps=deps, checkpointer=InMemorySaver())
    async with client(app) as c:
        a = await login(c)
        b = {"Authorization": "Bearer " + (await c.post("/auth/register", json={"email": "bob2@x.io", "password": "longenough1"})).json()["token"]}
        rid = (await c.post("/jobs/job-001/runs", headers=a)).json()["run_id"]
        await wait_status(c, a, rid, {"queued_degraded"})
        deps.port = SampleAdapter()
        assert (await c.post("/admin/retry-degraded", headers=b)).json() == {"retried": 0}     # bob cannot requeue alice's work
        assert (await c.get("/health")).json()["queued_degraded_runs"] == 1
        s = (await c.put("/settings", json={"minimum_project_budget_usd": 400, "auto_skip_low_fit": False}, headers=a)).json()
        assert s["minimum_project_budget_usd"] == 400
        assert (await c.put("/settings", json={"hourly_rate_usd": -3}, headers=a)).status_code == 422
        assert (await c.post("/settings/searches/churn", headers=a)).json()["saved_searches"] == ["churn"]
        assert (await c.get("/settings", headers=b)).json()["saved_searches"] == []             # per-user
        low_fit = (await c.post("/jobs/job-003/runs", headers=a)).json()["run_id"]
        assert await wait_status(c, a, low_fit, {"watching"}) == "watching"
        assert deps.port.submissions == {} and deps.port.balance == 100
        new = (await c.post("/jobs/job-001/runs", headers=a)).json()["run_id"]                  # budget ceiling 450 >= 400
        await wait_status(c, a, new, {"awaiting_approval"})
        s = (await c.put("/settings", json={"minimum_project_budget_usd": 500}, headers=a)).json()
        skipped = (await c.post("/jobs/job-001/runs", headers=a)).json()["run_id"]              # ceiling 450 < 500 now
        assert await wait_status(c, a, skipped, {"skipped"}) == "skipped"


async def test_reviewer_login_works_with_a_different_persona_set(make_deps, monkeypatch, tmp_path):
    """Regression: the seeded reviewer used a hard-coded persona id and silently failed on the generated corpus."""
    from dataprep.build_corpus import build
    build(tmp_path / "o", tmp_path / "d", seed=1, n_hist=60, n_stream=80, n_dev=10, n_clients=20)
    monkeypatch.setattr("apps.api.auth.users.DATA", tmp_path / "o")
    app = create_app(deps=make_deps(), checkpointer=InMemorySaver())
    async with client(app) as c:
        h = await login(c)
        me = (await c.get("/auth/me", headers=h)).json()
        assert me["freelancer_id"] in {"ai-ml-engineer", "fullstack-dev", "data-analyst"}
        assert {p["freelancer_id"] for p in (await c.get("/auth/personas")).json()} == {"ai-ml-engineer", "fullstack-dev", "data-analyst"}
