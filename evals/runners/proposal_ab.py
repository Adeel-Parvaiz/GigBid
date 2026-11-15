"""Matched proposal-copy experiment against the project's owned GigSim."""
from __future__ import annotations

import argparse
import json
import random
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from apps.gigsim.main import Simulator
from evals.common import ROOT, commit
from evals.metrics import wilson


def exact_mcnemar_pvalue(control_only: int, treatment_only: int) -> float:
    """Two-sided exact McNemar p-value from the discordant paired outcomes."""
    if control_only < 0 or treatment_only < 0:
        raise ValueError("discordant counts must be nonnegative")
    discordant = control_only + treatment_only
    if discordant == 0:
        return 1.0
    tail = min(control_only, treatment_only)
    term = 0.5**discordant
    cdf = term
    for k in range(1, tail + 1):
        term *= (discordant - k + 1) / k
        cdf += term
    return min(1.0, 2 * cdf)


def _proposal(job: dict, tailored: bool) -> dict:
    if tailored:
        skills = job["required_skills"]
        details = f" I would map the requirements across {', '.join(skills)}." if skills else ""
        text = (
            f"For {job['title']}, I would first clarify the requirements.{details} "
            "Then I would agree on a measurable baseline, deliver in milestones, and validate the result with you."
        )
    else:
        text = (
            "I would first clarify the requirements, agree on a measurable baseline, "
            "deliver in milestones, and validate the result with you."
        )
    budget = job.get("budget")
    amount = budget.get("min") if isinstance(budget, dict) else None
    if not isinstance(amount, (int, float)):
        amount = 100
    return {"job_id": job["job_id"], "cover_letter": text, "bid_amount": amount}


def run_experiment(data_dir: Path, database: Path, n: int, seed: int) -> dict:
    if n < 1:
        raise ValueError("n must be at least 1")
    simulator = Simulator(data_dir, database, connects=10**9, seed=seed)
    jobs = [
        job for job in simulator.adapter()._jobs.values()
        if isinstance(job.get("required_skills"), list) and job["required_skills"]
    ]
    jobs.sort(key=lambda job: job["job_id"])
    if n > len(jobs):
        raise ValueError(f"requested {n} jobs, but only {len(jobs)} have required skills")
    selected = random.Random(seed).sample(jobs, n)
    outcomes = {}
    draft_ids = {}

    for arm, tailored in (("generic", False), ("job_tailored", True)):
        account = f"proposal-ab-{arm}"
        for index, job in enumerate(selected):
            proposal = _proposal(job, tailored)
            draft = simulator.call(account, "create_proposal_draft", {
                "payload": proposal,
                "idempotency_key": f"{arm}-draft-{index}",
            })
            simulator.call(account, "submit_proposal", {
                "draft_id": draft["draft_id"],
                "idempotency_key": f"{arm}-submit-{index}",
            })
            draft_ids.setdefault(arm, []).append(draft["draft_id"])
        outcomes[arm] = simulator.call(account, "outcomes", {})

    if draft_ids["generic"] != draft_ids["job_tailored"]:
        raise RuntimeError("paired arms did not receive matching simulator draft IDs")
    if len(outcomes["generic"]) != n or len(outcomes["job_tailored"]) != n:
        raise RuntimeError("GigSim returned an unexpected number of outcomes")

    pairs = [
        {
            "job_id": job["job_id"],
            "generic_replied": bool(generic["replied"]),
            "job_tailored_replied": bool(tailored["replied"]),
        }
        for job, generic, tailored in zip(
            selected, outcomes["generic"], outcomes["job_tailored"], strict=True
        )
    ]
    control_only = sum(p["generic_replied"] and not p["job_tailored_replied"] for p in pairs)
    treatment_only = sum(p["job_tailored_replied"] and not p["generic_replied"] for p in pairs)
    counts = {
        arm: sum(bool(outcome["replied"]) for outcome in outcomes[arm])
        for arm in ("generic", "job_tailored")
    }
    p_value = exact_mcnemar_pvalue(control_only, treatment_only)
    alpha = 0.05
    provenance = Counter(str(job.get("provenance", "unspecified")) for job in selected)
    return {
        "experiment": "generic versus job-tailored proposal copy",
        "design": "matched pairs; both arms use the same jobs, bid amounts, GigSim seed, and draft-ID sequence",
        "seed": seed,
        "n": n,
        "job_provenance_counts": dict(sorted(provenance.items())),
        "reply_rates": {
            arm: {
                "replies": counts[arm],
                "submissions": n,
                "rate": counts[arm] / n,
                "wilson_95ci": wilson(counts[arm], n),
            }
            for arm in ("generic", "job_tailored")
        },
        "reply_rate_difference_job_tailored_minus_generic": (counts["job_tailored"] - counts["generic"]) / n,
        "paired_test": {
            "name": "exact two-sided McNemar test",
            "generic_only_replies": control_only,
            "job_tailored_only_replies": treatment_only,
            "p_value": p_value,
            "alpha": alpha,
            "significant": p_value < alpha,
        },
        "pairs": pairs,
        "limitations": [
            "GigSim outcomes are deterministic rule-based synthetic client decisions, not real reply-rate evidence.",
            "The treatment mentions the job title and listed required skills; the simulator rewards these signals by design.",
            "The experiment uses fixed copy templates and does not compare LLM prompt versions or establish generalization.",
            "Simulator submissions and Connects are isolated in a temporary local database; no external marketplace is contacted.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/processed/kaggle_2024_v1")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=4016)
    parser.add_argument("--output", type=Path, default=ROOT / "evals/results/proposal_ab_experiment.json")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="gigbid-proposal-ab-") as directory:
        result = run_experiment(args.data_dir, Path(directory) / "gigsim.sqlite", args.n, args.seed)
    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "commit": commit(),
            "corpus": f"seeded sample of {args.n} jobs with required skills from {args.data_dir.name}",
            "valid_for_real_marketplace_claims": False,
            "why_not": "owned GigSim's deterministic rule-based client model is a controlled comparison, not real client evidence",
        },
        **result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "n": args.n,
        "reply_rates": payload["reply_rates"],
        "paired_test": payload["paired_test"],
    }, indent=2))


if __name__ == "__main__":
    main()
