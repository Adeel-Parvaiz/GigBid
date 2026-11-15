import pytest

from worker.settings import (
    _cron_jobs_for_interval,
    _live_scheduled_reads_allowed,
)


def test_120_minute_schedule_runs_every_two_hours():
    jobs = _cron_jobs_for_interval(120)

    assert [(job.hour, job.minute) for job in jobs] == [
        (hour, 0) for hour in range(0, 24, 2)
    ]


def test_90_minute_schedule_preserves_interval_across_hour_boundaries():
    jobs = _cron_jobs_for_interval(90)

    assert [(job.hour, job.minute) for job in jobs] == [
        (0, 0), (1, 30), (3, 0), (4, 30), (6, 0), (7, 30), (9, 0), (10, 30),
        (12, 0), (13, 30), (15, 0), (16, 30), (18, 0), (19, 30), (21, 0), (22, 30),
    ]


@pytest.mark.parametrize(
    ("interval", "explicitly_enabled", "expected"),
    [(5, True, False), (119, True, False), (120, True, True), (120, False, False)],
)
def test_live_schedule_requires_opt_in_and_120_minute_interval(interval, explicitly_enabled, expected):
    assert _live_scheduled_reads_allowed(interval, explicitly_enabled) is expected


@pytest.mark.parametrize("interval", [0, -5, 61])
def test_invalid_or_unrepresentable_schedule_interval_is_rejected(interval):
    with pytest.raises(ValueError):
        _cron_jobs_for_interval(interval)
