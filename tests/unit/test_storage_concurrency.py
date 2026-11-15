from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from apps.api.auth.users import UserStore
from apps.api.runs import RunStore


def test_parallel_run_updates_preserve_owner_ids_and_timestamps():
    store, start = RunStore(), Barrier(8)

    def exercise(index):
        start.wait()
        owner = f"user-{index}"
        run = store.create(owner, "bid", f"job-{index}")
        for version in range(30):
            store.update(run["run_id"], status="running", outcome=str(version))
            store.put_settings(owner, {"version": version})
            saved = store.get(run["run_id"])
            assert saved["run_id"] == run["run_id"] and saved["user_id"] == owner
            assert saved["created_at"] == run["created_at"]
            assert store.get_settings(owner) == {"version": version}
            assert [r["run_id"] for r in store.list(owner)] == [run["run_id"]]
        return run["run_id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(exercise, range(8)))
    assert len(set(ids)) == 8


def test_parallel_registration_and_login_preserve_user_identity():
    users, start = UserStore(), Barrier(8)
    persona = next(iter(users._personas))

    def exercise(index):
        start.wait()
        email = f"concurrent-{index}@example.test"
        user = users.create(email, "concurrency-password", persona)
        for _ in range(4):
            assert users.login(email, "concurrency-password")["user_id"] == user["user_id"]
            assert users.verify(users.issue(user["user_id"]))["email"] == email
        return user["user_id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert len(set(pool.map(exercise, range(8)))) == 8
