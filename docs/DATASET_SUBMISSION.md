# Dataset submission notes

The dataset portion uses one permitted real source, supplemented with explicitly synthetic supporting data. Combining the six candidates is optional. Dataset selection, comparisons, attribution, licensing and limitations are in [DATA_CARD.md](DATA_CARD.md).

## Report-ready description

GigBid uses asaniczka's Upwork Job Postings Dataset 2024 (50K Records), Kaggle version 1, downloaded on 2026-11-11. Kaggle displayed ODC-By; this does not independently establish rights to upstream scraped content. The original ZIP SHA-256 is `3f40f06c267f6429e6c9fdd9a81c0c9bb3a3c9eb85edadb1d6638394e9ce5b35`.

Preprocessing retained 49,699 of 53,058 CSV rows after heuristic English filtering and near-duplicate removal. Text was cleaned and recognizable contacts redacted; skills and categories were inferred from a local lexicon. With seed 7, 3,000 distinct real posts were sampled: 1,500 historical pricing records and 1,500 stream records. The stream additionally contains 1,500 synthetic normal posts, 153 generated scam/injection posts and 37 generated duplicate variants, totaling 3,190 stream records. The supporting corpus includes 400 synthetic clients, three freelancer personas, 88 portfolio items, 450 past proposals and 30 conversations. Reviews appear as synthetic portfolio evidence. Generated fields attached to real jobs are identified separately from source facts.

Each persona has 200 synthetic development examples with rule-derived gold labels. Neither these labels nor simulated reply/hire outcomes are observations from Kaggle or the real marketplace. The source provides no currency column; imported USD amounts are an explicit system assumption and pricing statistics are exploratory. The corpus does not establish real-world decision accuracy or marketplace outcomes.

## Reproduce and demonstrate

Follow [README.md](../README.md#run-with-the-assignment-dataset). The archive must be downloaded separately; raw and processed records are excluded from version control. The scripts reject a different archive checksum instead of silently using another dataset version. `scripts.prepare_dataset --verify` independently re-ingests the ZIP and rebuilds every corpus/dev output in a temporary directory. The API launcher explicitly selects the Kaggle corpus for marketplace and portfolio loading.

## Scope of completion

The dataset requirements in the supplied assignment excerpt are covered by the source selection, ingestion pipeline, real/synthetic provenance, supporting generated data and data card. No extra dataset or invented human labels are needed to claim completion of those requirements. Upstream rights and the source's unstated currency cannot be independently resolved by this code. Human-labelled real examples, external instructor tests and real outcome evaluation remain separate evaluation work; they must not be represented as completed.

## Validation on 2026-11-14

- Full source reproduction passed: `python -m scripts.prepare_dataset --verify` checked the archive checksum, independently ingested 53,058 rows (49,699 retained), rebuilt the corpus and all three dev sets, compared their content and validated manifest file hashes. Existing data and evaluation artifacts were preserved.
- Marketplace/portfolio loading: 3,190 agent-visible jobs and 538 portfolio/proposal records; job gold labels are excluded from the marketplace view.
- Dataset tests: 16 passed using `python -m pytest --confcutdir=tests/unit --basetemp=data/processed/dataset-check-tests-final -p no:cacheprovider tests/unit/test_dataprep_ingest.py tests/unit/test_dataprep_corpus.py -q -k 'not hourly_jobs'`.
- The original isolated Windows run excluded the graph-level hourly pricing test because Application Control blocked `ormsgpack`. The latest WSL suite records **103 passed, 2 skipped** in `evals/results/playwright_validation.json`; the earlier 101-test run remains in `real_agent_behaviour_tests.json`. Separately, 25 real-model API checks and 8 Chromium browser tests pass in `real_agent_behaviour.json` and `playwright.json`. Infrastructure-dependent skips do not establish Postgres/Redis durability.
- New scripts pass Ruff; Compose YAML parses and propagates the corpus directory to all four Python services. Containers were not started.
- An explicitly requested missing real-job input now fails immediately instead of silently generating an entirely synthetic corpus.
