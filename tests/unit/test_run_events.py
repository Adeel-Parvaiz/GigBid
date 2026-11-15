from apps.api.runs import RunStore


def test_run_events_are_shared_and_sequenced_across_store_instances(tmp_path):
    database = str(tmp_path / "runs.sqlite")
    writer = RunStore(database)
    run = writer.create("user-1", "bid", "job-1")
    reader = RunStore(database)

    first = writer.append_event(run["run_id"], {"type": "started"})
    second = reader.append_event(run["run_id"], {"type": "done", "status": "skipped"})

    assert first["seq"] == 1
    assert second["seq"] == 2
    assert reader.events_after(run["run_id"], 1) == [second]

    writer.db.close()
    reader.db.close()
