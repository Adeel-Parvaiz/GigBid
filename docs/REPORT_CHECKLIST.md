# R&D report checklist (<= 10 pages). Every claim -> a results file, trace or commit.
1 Problem/constraints: what must never be automated (send, spend Connects), budgets (declare p95 latency + cost).
2 Architecture: use docs/ARCHITECTURE.md diagrams.
3 R&D A tool granularity: run complete in `evals/rd_a/` with 40 contract-derived tasks, three description-only conditions, 120 local MCP calls, individual and aggregate results, and a visualization. This is a BM25 lexical tool-discovery baseline, not an LLM/production-agent comparison; see `docs/RD_A_RESULTS.md` for measured results and limitations.
4 R&D B RAG: retrieval and decision runs exist for all three personas against `evals/datasets/kaggle_2024_v1`; the local-simulator outcome runner and a hashing-vs-local-FastEmbed comparison also completed. See `docs/RD_B_RESULTS.md` for the FastEmbed model/revision, re-embedded corpus, retrieval/decision/claim metrics, and paired cases where decisions did not improve or regressed despite retrieval changes. All current dev/gold data are synthetic; the instructor dev set and real-world outcome evaluation are still outstanding.
5 R&D C single agent vs supervisor vs graph: completed on the frozen 50-job synthetic sample (150 paired trials). See `docs/RD_C_RESULTS.md`, `evals/results/rd_c_comparison.json`, and `evals/results/rd_c_trials.jsonl` for aggregate and persona/job-type results, five counted failures, and simulator-only outcome limitations. The hand-built graph scored 0.98 bid/skip accuracy versus 0.34 ReAct and 0.36 supervisor; the approved-proposal trace documents a baseline injection false positive that passed the local guard. This is exploratory synthetic evidence, not a real-market comparison. Open-model selection evidence remains separate: `docs/OPEN_MODEL_RESULTS.md` and `evals/results/open_model_comparison.json`.
6 Change request (2 Nov): not received. Rules/prompts/thresholds are in `agent/config.yaml`; measure lines changed + minutes.
7 Extension: not built.
8 Failure analysis: actual failed cases now exist in `docs/OPEN_MODEL_RESULTS.md` and real API defects in `docs/REAL_AGENT_BEHAVIOUR.md`; the final report still needs >= 10 failed dev jobs grouped into a taxonomy, with the attempted fix and measured outcome.
9 Safety: use "Safety properties" in ARCHITECTURE.md; add the injection blind spot from `injection_eval.json`.
10 Hidden test results vs declared budgets, no excuses.
Also: judge calibration (30 own labels, Cohen's kappa: `evals/runners/judge_calibration.py`), human pairwise panel, cost per proposal.

Actual behavior evidence: `evals/results/real_agent_behaviour.json` records 25 passed real-model HTTP checks; `docs/REAL_AGENT_BEHAVIOUR.md` explains the defects found and fixed. This includes SQLite pending-approval restart coverage and local mock writes, not a substitute for GigSim/Postgres/Redis, browser tests or public traces.
Browser evidence is now separate: `evals/results/playwright.json` and `docs/FRONTEND_TESTS.md` record 8 passed Chromium tests (desktop plus phone sign-in), with local HTML output under `apps/web/playwright-report`. Browser fixtures use sample data/HeuristicLLM; no real-model or live-marketplace browser outcome claim is made. This was a local WSL run, not a hosted CI run.

## Data section (required by the TA post): dataset selection, preprocessing, attribution, licensing, limitations
Use `docs/DATA_CARD.md`. Dataset #1 (Kaggle v1, ODC-By displayed) has been downloaded and ingested; raw data stays git-ignored. The versioned corpus and synthetic-only dev sets are under `data/processed/kaggle_2024_v1` and `evals/datasets/kaggle_2024_v1`.

Before submitting:
- Follow `README.md`'s assignment dataset instructions; `scripts.prepare_dataset --verify` checks independent ingestion/build reproduction and `scripts.run_dataset --check` checks marketplace/portfolio loading. Report-ready dataset text is in `docs/DATASET_SUBMISSION.md`.
- Reproduce the corpus build and cite the source/version/checksum and exact retained/sampled counts from its manifest.
- Retrieval/decision evaluations have been rerun against the generated dev sets; rerun after further changes. State explicitly that those labels are synthetic/rule-derived and are not labels supplied by Kaggle.
- Do not report real reply/hire performance: the Kaggle job posts have no outcomes, and local simulator rates are not marketplace behavior.
- Explain the source's missing currency field; current USD parsing is an assumption and price statistics are exploratory.
- Preserve the ODC-By attribution and do not commit/redistribute raw records without checking upstream rights and terms.
