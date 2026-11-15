from evals.rd_a.run_experiment import DESCRIPTIONS, SERVER_FOR_TOOL, load_tasks


def test_rd_a_has_exactly_40_unique_tasks_and_all_conditions_cover_same_tools():
    data = load_tasks()
    tasks = data["tasks"]
    assert len(tasks) == 40
    assert len({task["task_id"] for task in tasks}) == 40
    assert set(DESCRIPTIONS) == {"fine_grained", "coarse_grained", "optimized"}
    assert all(set(descriptions) == set(SERVER_FOR_TOOL) for descriptions in DESCRIPTIONS.values())
    assert {task["expected_tool"] for task in tasks} == set(SERVER_FOR_TOOL)


def test_rd_a_task_intents_have_reproducible_ids_and_complete_call_contracts():
    tasks = load_tasks()["tasks"]
    assert all(task["request"].strip() for task in tasks)
    assert all(task["arguments"] is not None and task["expect"] for task in tasks)
