"""Real Redis + real arq worker subprocess. Skipped if redis-server is not installed."""
import asyncio
import os
import shutil
import subprocess
import sys
import time

import pytest
from arq import create_pool
from arq.connections import RedisSettings

from apps.api.auth.users import UserStore
from apps.api.runs import RunStore
from tests.conftest import free_port

pytestmark = pytest.mark.skipif(shutil.which("redis-server") is None, reason="redis-server not installed")


@pytest.fixture
def env(tmp_path):
    port = free_port()
    redis = subprocess.Popen(["redis-server", "--port", str(port), "--save", "", "--appendonly", "no"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.6)
    e = {**os.environ, "REDIS_URL": f"redis://127.0.0.1:{port}/0", "RUNS_DB": str(tmp_path / "runs.sqlite"),
         "USERS_DB": str(tmp_path / "users.sqlite"), "DATABASE_URL": f"sqlite:///{tmp_path / 'ckpt.sqlite'}"}
    uid = UserStore(e["USERS_DB"]).create("w@x.io", "longenough1", "sample-ai-engineer")["user_id"]
    yield {"env": e, "port": port, "uid": uid, "runs_db": e["RUNS_DB"]}
    redis.terminate()


def start_worker(env):
    return subprocess.Popen([sys.executable, "-m", "arq", "worker.settings.WorkerSettings"], env=env["env"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def pool(env):
    return await create_pool(RedisSettings(port=env["port"]))


async def test_analyse_scout_and_restart_never_double_analyse(env):
    w = start_worker(env)
    try:
        p = await pool(env)
        uid = env["uid"]
        job = await p.enqueue_job("analyse_job", uid, "job-001", _job_id=f"analyse:{uid}:job-001")
        r1 = await job.result(timeout=30)
        assert r1["status"] == "awaiting_approval"                     # stopped at the human gate, nothing sent
        assert await p.enqueue_job("analyse_job", uid, "job-001", _job_id=f"analyse:{uid}:job-001") is None   # redis-level dedupe
    finally:
        w.terminate()
        w.wait(10)
    # --- worker killed and restarted; the same work is enqueued again under a different redis job id ---
    w2 = start_worker(env)
    try:
        p = await pool(env)
        r2 = await (await p.enqueue_job("analyse_job", uid, "job-001", _job_id="retry-after-restart")).result(timeout=30)
        assert r2["run_id"] == r1["run_id"]                            # reused, not re-analysed
        RunStore(env["runs_db"]).add_search(uid, "churn")
        s = await (await p.enqueue_job("scout", uid, "churn")).result(timeout=30)
        assert s["enqueued"] == []                                     # job-001 already has a live run
        s = await (await p.enqueue_job("scout", uid, "classifier")).result(timeout=30)
        assert sorted(s["enqueued"]) == ["job-004", "job-005"]          # NEW jobs matching the query: one analyse job each
        for _ in range(100):
            if all(RunStore(env["runs_db"]).find_active(uid, "bid", j) for j in ("job-004", "job-005")):
                break
            await asyncio.sleep(0.2)
    finally:
        w2.terminate()
        w2.wait(10)
    rows = RunStore(env["runs_db"]).list(uid)
    assert sorted(r["target"] for r in rows) == ["job-001", "job-004", "job-005"]  # exactly one run per job, ever
