import json

import httpx
from langgraph.checkpoint.memory import InMemorySaver

from apps.api.main import create_app
from worker.settings import execute_queued_run, resume_queued_run


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_job(self, name, *args, **kwargs):
        self.jobs.append((name, args, kwargs))
        return object()


def client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def login(c):
    response = await c.post(
        "/auth/login", json={"email": "reviewer@gigbid.test", "password": "reviewer-pass-1"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def run_events(c, headers, run_id):
    events = []
    async with c.stream("GET", f"/runs/{run_id}/events", headers=headers) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


async def test_job_run_is_enqueued_without_starting_api_task(make_deps):
    app = create_app(deps=make_deps(), checkpointer=InMemorySaver())
    queue = FakeQueue()
    app.state.arq_pool = queue

    async with client(app) as c:
        headers = await login(c)
        response = await c.post("/jobs/job-001/runs", headers=headers)

    assert response.status_code == 202
    run = response.json()
    assert queue.jobs == [
        ("execute_queued_run", (run["run_id"],), {"_job_id": f"run:{run['run_id']}"})
    ]
    assert app.state.manager.tasks == set()
    assert app.state.manager.store.get(run["run_id"])["origin"] == "worker"


async def test_approval_resume_is_enqueued_and_claimed_once(make_deps):
    app = create_app(deps=make_deps(), checkpointer=InMemorySaver())
    async with client(app) as c:
        headers = await login(c)
        run = (await c.post("/jobs/job-001/runs", headers=headers)).json()
        events = await run_events(c, headers, run["run_id"])
        assert events[-1]["type"] == "interrupt"
        queue = FakeQueue()
        app.state.arq_pool = queue

        response = await c.post(
            f"/runs/{run['run_id']}/approval", json={"action": "approve"}, headers=headers
        )
        duplicate = await c.post(
            f"/runs/{run['run_id']}/approval", json={"action": "approve"}, headers=headers
        )

    assert response.status_code == 202
    assert response.json()["status"] == "running"
    assert duplicate.status_code == 409
    assert len(queue.jobs) == 1
    name, args, _ = queue.jobs[0]
    assert name == "resume_queued_run"
    assert args[0] == run["run_id"]
    assert args[1]["action"] == "approve"


async def test_worker_executes_and_resumes_a_precreated_run_once(make_deps):
    deps = make_deps()
    app = create_app(deps=deps, checkpointer=InMemorySaver())
    async with client(app) as c:
        headers = await login(c)
    user = app.state.users.verify(headers["Authorization"].removeprefix("Bearer "))
    run, created = await app.state.manager.prepare_worker(user, "bid", "job-001")
    assert created is True
    context = {"manager": app.state.manager, "users": app.state.users}

    started = await execute_queued_run(context, run["run_id"])
    assert started["status"] == "awaiting_approval"
    assert app.state.manager.store.claim_status(
        run["run_id"], user["user_id"], "awaiting_approval", "running"
    )
    resumed = await resume_queued_run(context, run["run_id"], {"action": "approve"})
    duplicate = await resume_queued_run(context, run["run_id"], {"action": "approve"})

    assert resumed["status"] == "submitted"
    assert duplicate["status"] == "submitted"
    assert len(deps.port.submissions) == 1
