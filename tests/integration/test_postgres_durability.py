"""C6 on a real Postgres: run to the approval gate, 'crash' (drop everything), resume, submit once.
Skipped when no Postgres is reachable (set TEST_DATABASE_URL)."""
import json
import os
import uuid

import httpx
import pytest
from dotenv import dotenv_values
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph, pending_approval
from agent.persistence import make_checkpointer
from apps.api.main import create_app
from apps.api.runs import RunStore
from tests.conftest import cfg_of

CONFIGURED_URL = os.environ.get("TEST_DATABASE_URL") or dotenv_values().get("TEST_DATABASE_URL")
URL = CONFIGURED_URL or "postgresql://gigbid:gigbid@localhost:5432/gigbid"


async def reachable() -> bool:
    try:
        async with make_checkpointer(URL):
            return True
    except Exception as error:
        if CONFIGURED_URL:
            pytest.fail(
                f"TEST_DATABASE_URL is configured but PostgreSQL checkpointer setup failed "
                f"({type(error).__name__})"
            )
        return False


async def test_crash_and_resume_on_postgres_submits_once(make_deps, profile):
    if not await reachable():
        pytest.skip("no postgres")
    deps, tid = make_deps({"budgets": {"max_tokens_per_job": 50000}}), f"pg-{uuid.uuid4().hex[:8]}"
    async with make_checkpointer(URL) as saver:
        await build_bid_graph(deps, saver).ainvoke({"job_id": "job-001", "profile": profile}, cfg_of(tid))
    async with make_checkpointer(URL) as saver:                       # new connection = restarted process
        g = build_bid_graph(deps, saver)
        assert await pending_approval(g, cfg_of(tid))
        out = await g.ainvoke(Command(resume={"action": "approve"}), cfg_of(tid))
        history = [s async for s in g.aget_state_history(cfg_of(tid))]
    assert out["status"] == "submitted" and len(deps.port.submissions) == 1
    assert len(history) > 5                                           # replayable from any node


async def test_api_restart_with_pending_postgres_approval_submits_once(make_deps, tmp_path):
    if not await reachable():
        pytest.skip("no postgres")

    def client(app):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")

    async def login(c):
        response = await c.post("/auth/login", json={"email": "reviewer@gigbid.test", "password": "reviewer-pass-1"})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['token']}"}

    async def finish_events(c, headers, run_id):
        items = []
        async with c.stream("GET", f"/runs/{run_id}/events", headers=headers) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    items.append(json.loads(line[6:]))
        return items

    deps, run_db = make_deps({"budgets": {"max_tokens_per_job": 50000}}), str(tmp_path / "runs.sqlite")
    market = deps.port
    async with make_checkpointer(URL) as checkpointer:
        app1 = create_app(deps=deps, checkpointer=checkpointer, run_store=RunStore(run_db))
        async with client(app1) as c:
            headers = await login(c)
            run = (await c.post("/jobs/job-001/runs", headers=headers)).json()
            first_events = await finish_events(c, headers, run["run_id"])
            assert first_events[-1]["type"] == "interrupt"
            user_store = app1.state.users
        app1.state.manager.store.db.close()  # simulate the API process exiting

    async with make_checkpointer(URL) as checkpointer:
        app2 = create_app(
            deps=deps,
            checkpointer=checkpointer,
            run_store=RunStore(run_db),
            users=user_store,
            seed=False,
        )
        async with client(app2) as c:
            headers = await login(c)
            pending = (await c.get("/approvals/pending", headers=headers)).json()
            assert [item["run"]["run_id"] for item in pending] == [run["run_id"]]
            assert pending[0]["payload"]["dry_run"]["dry_run"] is True
            response = await c.post(f"/runs/{run['run_id']}/approval", json={"action": "approve"}, headers=headers)
            assert response.status_code == 202
            resumed_events = await finish_events(c, headers, run["run_id"])
            assert resumed_events[-1]["type"] == "done" and resumed_events[-1]["status"] == "submitted"
            detail = (await c.get(f"/runs/{run['run_id']}", headers=headers)).json()
            assert detail["status"] == "submitted"

    assert len(market.submissions) == 1 and market.balance == 92
