# Signature extension: X2 proposal experiments

GigBid's signature extension is a reproducible, paired A/B comparison of two
proposal-copy strategies in the project-owned GigSim:

- **Control — generic:** a short, project-oriented message with the same scope,
  milestones, validation plan, and bid as the treatment.
- **Treatment — job-tailored:** names the job title and listed required skills,
  then uses the same scope, milestones, validation plan, and bid.

Run the experiment from the repository root:

```powershell
python -m evals.runners.proposal_ab --n 200 --seed 4016
```

The runner samples jobs with required skills, runs both strategies against the
same jobs, and gives each arm matching draft IDs so the deterministic simulator
uses common random draws. It stores paired reply outcomes, per-arm reply rates
and Wilson intervals, and the **exact two-sided McNemar test** in
[`evals/results/proposal_ab_experiment.json`](../evals/results/proposal_ab_experiment.json).
The result records source provenance and whether the paired reply difference is
significant at alpha 0.05. Re-run with a different seed as a sensitivity check;
the seed is part of the output.

The runner uses a temporary SQLite database and synthetic account IDs. Its
simulator submissions spend only temporary Connects, make no external calls,
and do not bypass GigBid's approval gate in the product. Both variants are
fixed templates, not LLM prompt versions.

## Recorded run

The checked-in run used 200 seeded jobs (seed 4016) from the versioned
`kaggle_2024_v1` data directory:

| Strategy | Replies / submissions | Reply rate | Wilson 95% interval |
|---|---:|---:|---:|
| Generic | 36 / 200 | 18.0% | 13.3–23.9% |
| Job-tailored | 158 / 200 | 79.0% | 72.8–84.1% |

The matched difference was +61 percentage points. Exact two-sided McNemar:
8 generic-only versus 130 job-tailored-only replies, **p = 1.62 × 10⁻²⁹**
(alpha 0.05). The strong difference is expected under this simulator because
its scoring rule explicitly rewards the treatment's skill/title mentions. It
is evidence that the A/B harness and significance test ran—not a real-market
performance claim. Full paired observations and source counts are in the
[machine-readable result](../evals/results/proposal_ab_experiment.json).

## What this measures—and does not

The owned GigSim client model is deterministic and rule-based. Its reply
probability explicitly rewards mentioning required skills and job-title terms,
so this experiment measures response to those signals under that simulator's
assumptions. The paired test quantifies this controlled synthetic comparison;
it does not establish real-client performance or generalization. The job
sample may include both public job text and synthetic records, while all
client preferences and reply outcomes are synthetic.

The raw paired rows make the result auditable without presenting it as live
marketplace evidence. This extension is separate from the human-approved,
non-sending-by-default product workflow.

Focused regression tests:

```powershell
python -m pytest -q tests/unit/test_proposal_ab.py
```
