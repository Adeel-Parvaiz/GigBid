import json
from collections import Counter

from evals.runners.rd_c_comparison import SAMPLE_PATH, select_sample


def test_rd_c_sample_is_frozen_stratified_and_unique():
    frozen = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    assert select_sample() == frozen

    jobs = frozen["jobs"]
    assert len(jobs) == 50
    assert len({job["job_id"] for job in jobs}) == 50
    assert Counter(job["persona"] for job in jobs) == {
        "ai-ml-engineer": 17,
        "data-analyst": 17,
        "fullstack-dev": 16,
    }
    assert Counter(job["job_type"] for job in jobs) == {
        "ordinary": 30,
        "scam": 10,
        "injection": 10,
    }


def test_watch_is_counted_as_skip_for_accuracy():
    from evals.runners.rd_c_comparison import _accuracy_action

    assert _accuracy_action("watch") == "skip"
    assert _accuracy_action("bid") == "bid"


def test_gigsim_reply_rate_includes_its_denominator():
    from evals.runners.rd_c_comparison import _reply_cell

    assert _reply_cell({"gigsim_replies": 1, "gigsim_submissions": 1, "gigsim_reply_rate": 1}) == "1/1 (100.0%)"
    assert _reply_cell({"gigsim_replies": 0, "gigsim_submissions": 0, "gigsim_reply_rate": None}) == "0/0 (n/a)"
