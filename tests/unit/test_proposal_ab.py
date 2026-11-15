from pathlib import Path

import pytest

from evals.runners.proposal_ab import exact_mcnemar_pvalue, run_experiment

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("control_only", "treatment_only", "expected"),
    [(0, 0, 1.0), (5, 0, 0.0625), (6, 0, 0.03125), (2, 2, 1.0)],
)
def test_exact_mcnemar_pvalue(control_only, treatment_only, expected):
    assert exact_mcnemar_pvalue(control_only, treatment_only) == pytest.approx(expected)


def test_experiment_pairs_both_strategies_on_the_same_jobs(tmp_path):
    result = run_experiment(ROOT / "data/sample", tmp_path / "gigsim.sqlite", n=3, seed=4016)

    assert result["n"] == 3
    assert len(result["pairs"]) == 3
    assert result["reply_rates"]["generic"]["submissions"] == 3
    assert result["reply_rates"]["job_tailored"]["submissions"] == 3
    assert result["paired_test"]["name"] == "exact two-sided McNemar test"
    assert all(pair["job_id"] for pair in result["pairs"])
