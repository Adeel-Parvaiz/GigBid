# Data card

**Status:** Kaggle dataset #1 below has been downloaded and ingested; the other five are not used in the current corpus. Kaggle page metadata and the downloaded file were checked on **2026-11-11**. Kaggle's displayed license is not proof that the uploader had rights to redistribute source-platform data.

## 1. Dataset comparison and selection

| Dataset (Kaggle author and title) | Kaggle description / displayed license | GigBid fit and decision |
|---|---|---|
| [asaniczka, Upwork Job Postings Dataset 2024 (50K Records)](https://www.kaggle.com/datasets/asaniczka/upwork-job-postings-dataset-2024-50k-records) | Described as 50,000 Upwork postings collected over two weeks. Version 1; **ODC Attribution License (ODC-By)** displayed. The downloaded CSV has 53,058 rows. | **Selected and ingested** for real job text. The CSV schema was inspected; currency is not a column, so budget-derived pricing has that limitation. |
| [asaniczka, All Upwork Job Postings - Monthly Tracker](https://www.kaggle.com/datasets/asaniczka/all-jobs-on-upwork-200k-plus) | Described as 200k+ Upwork postings collected minute by minute; metadata says the latest version was updated 2024-07-25. **ODC Attribution License (ODC-By)** displayed. | Alternative or time-series source, **not an automatic addition** to the primary: repeated observations and overlap with other Upwork collections can overweight jobs and leak near-duplicates across splits. Use only after examining snapshot IDs/dates and deduplicating against every other source. |
| [Ahmed Myalo, Upwork freelance jobs (+60k)](https://www.kaggle.com/datasets/ahmedmyalo/upwork-freelance-jobs-60k) | Described as 60k+ jobs from 2023; Kaggle lists CSV and XLSX files. **Apache 2.0** displayed. | Possible secondary job-text source, but older and likely overlapping. Prefer the CSV; the current ingestion CLI accepts CSV, not XLSX. Use only after schema and license-scope checks. |
| [asaniczka, Freelance Contracts Dataset (1.3 Million Entries)](https://www.kaggle.com/datasets/asaniczka/freelance-contracts-dataset-1-3-million-entries) | Described as contracts with job IDs/titles/dates, freelancer IDs, hours worked, amount paid, and hourly rates; it says “a leading freelancing platform” but does not identify it in the metadata reviewed. **ODC Attribution License (ODC-By)** displayed. | **Not a job-post input.** Consider only for exploratory realized-contract analysis after checking platform, units, selection bias, and field semantics. Contract rates and payouts are not interchangeable with posted client budgets or bid/hire outcomes. |
| [Sarvesh Chhetri, Freelancer Marketplace Dataset for ML & Analytics](https://www.kaggle.com/datasets/sarveshchhetri/freelancer-success-earnings-and-churn-prediction) | Described as 12,000 “realistic” freelancer records for 2025; Kaggle tags it synthetic. **Apache 2.0** displayed. | Do not treat as observed freelancer behavior or real outcomes. It could be an optional synthetic comparison set, kept separate and attributed; it is not needed for the primary job corpus. |
| [Aditya_M_Mantri, Fake-Job-Posting-Detection](https://www.kaggle.com/datasets/adityammantri/trial-1) | Described as global labeled real/fake and unlabeled job posts. **License: Unknown** displayed. | **Do not download for use or redistribute until licensing is clarified.** If resolved, consider only as a separate external fraud-evaluation set after validating label definitions, provenance, overlap, and compatibility with GigBid scam labels. It is not Upwork-specific. |

**Selection:** Dataset #1 is the only listed source currently included. Its raw archive is kept locally at `data/raw/upwork-job-postings-2024-v1.zip` and is git-ignored; the processed corpus is generated under `data/processed/kaggle_2024_v1`. The importer retained 49,699 rows; with seed 7, the corpus builder sampled 3,000 distinct real posts (1,500 historical and 1,500 stream). To keep the rule-labelled development examples runnable through the normal marketplace and simulator adapters, the stream also includes 1,500 synthetic normal jobs, 153 synthetic scam/injection posts, and 37 generated duplicate variants (15 derived from real posts and 22 from synthetic posts in this build). Dev examples are sampled from synthetic jobs already in that stream; only synthetic examples receive rule-derived gold. Do not combine the other job-post datasets by default: their coverage likely overlaps and can overweight jobs or leak duplicates across splits. Contracts and freelancer-profile data are different data units and are not mixed into this job corpus.

## 2. Attribution, licensing, and handling

The ingested source citation is: **asaniczka, “Upwork Job Postings Dataset 2024 (50K Records),” Kaggle, https://www.kaggle.com/datasets/asaniczka/upwork-job-postings-dataset-2024-50k-records, version 1, accessed 2026-11-11, Kaggle-displayed ODC Attribution License (ODC-By)**. The downloaded archive is 21,509,465 bytes; SHA-256: `3f40f06c267f6429e6c9fdd9a81c0c9bb3a3c9eb85edadb1d6638394e9ce5b35`. Recheck the license and dataset version before redistribution.

The displayed license may not cover upstream content or resolve rights in scraped listings. Before use, inspect the dataset's own license/terms and provenance notes, and check applicable Upwork/platform terms and privacy obligations. The Upwork datasets describe scraped or collected marketplace posts; GigBid did not scrape Upwork. Do not represent Kaggle hosting as Upwork endorsement or permission.

Keep downloaded originals in `data/raw/` (git-ignored and not redistributed by default). The filename, version, download date, license, checksum, and citation are recorded in `data/raw/README.md` and this card. The Kaggle archive contains `upwork-jobs.csv` with columns `title`, `link`, `description`, `published_date`, `is_hourly`, `hourly_low`, `hourly_high`, `budget`, and `country`. The importer does not retain the `link` field and redacts recognizable email addresses and phone numbers in titles/descriptions; this heuristic may miss or over-redact unusual formats. The processed corpus does not require client names or freelancer identifiers.

## 3. Real vs synthetic: identify both

Each job in the generated corpus carries `provenance: "real" | "synthetic"`. A real post is augmented with synthetic system-only fields, recorded in its `synthetic_fields`: `client_id` and generated client history, `duration_days`, `screening_questions`, `connects_cost`, and `warning_signals`. These are not source facts.

| Artefact | Real source material | Synthetic or derived material |
|---|---|---|
| Job title, description, budget, country, and date | From the Kaggle CSV when present; post text is contact-redacted | Missing fields remain missing/unknown; the synthetic generator creates separate top-up posts |
| Required skills and category | Derived heuristically from text using the local skill lexicon | Generation-time tags on generated posts |
| Clients, client history, hidden preferences | Never sourced from the listed public datasets; real jobs are assigned a synthetic client id | Always generated |
| Freelancer personas, portfolios, past proposals, and outcomes | Never sourced by the current pipeline | Generated; proposal outcomes are formula-sampled |
| Conversations and simulated replies | Never | Generated; replies use local simulation rules |

Real Kaggle posts have no scam/injection, bid/skip, evidence, reply, or hire labels in the source. Those labels are not assigned to real jobs. The dev files contain selected synthetic stream jobs; their gold labels are rule-derived, not human-labelled. The 12k Kaggle freelancer table is itself described/tagged as synthetic and must not be relabeled real if used in a separate experiment.

## 4. Preprocessing and ingestion

The current path is `dataprep/ingest.py` → `dataprep/build_corpus.py`. The selected dataset was read from its ZIP archive with the source-specific mapping `dataprep/mappings/upwork_2024_50k.yaml`. The archive contains exactly one CSV; ambiguous ZIPs fail rather than choosing an arbitrary file.

1. The source schema was inspected and mapped to title/description/date/payment fields. `inspect` supports ZIP input and an explicit `--mapping`; edit a source-specific mapping if another file differs.
2. Clean HTML entities/tags and whitespace, then redact recognizable email/phone contacts from title and description. The pass replaced 42 email-looking values and 379 phone-pattern matches in the retained JSONL; phone-pattern matches can include non-contact numeric text. Drop rows without a title or with descriptions shorter than 60 characters; apply the current English-token and ASCII filters. These are heuristic filters and may exclude valid non-English posts.
3. This source has 53,058 CSV rows. The importer retained 49,699, dropped 1,538 by its language filter and 1,821 near-duplicates. It parses numeric budgets and hourly ranges; unknown budget stays zero. **There is no currency column, and the importer currently labels parsed values USD without row-level confirmation.** Treat market price statistics from this dataset as exploratory; do not claim the source explicitly states currency.
4. Extract skills from title/description with `dataprep/skills.yaml`, then assign a category. The importer currently does not use a source-provided skills or URL column even if the generic mapping detects one.
5. Remove near-duplicates using a hash of the set of content words in the title and first 60 description words. This can merge distinct posts; it does not identify all repeated snapshots or cross-source duplicates reliably. Review before evaluation splitting.
6. `build_corpus` samples 1,500 real posts for historical pricing and 1,500 for the stream, tops the stream up with 1,500 synthetic normal jobs, adds generated scams/injections and duplicate variants, and computes market statistics from historical items with nonzero budgets. Duplicate variants are marked in `synthetic_fields`; unique source counts exclude them. Dev sets sample synthetic jobs already in the stream so marketplace and local-simulator evaluation can load them; real posts do not receive fabricated gold labels. Generated clients and outcomes are not real-world observations.

`data/processed/kaggle_2024_v1/DATA_MANIFEST.json` records seed, source/provenance counts, generated-label counts, and output hashes. The archive is version 1. The app still defaults to the small sample corpus; set `GIGBID_DATA_DIR` to the versioned output directory to run it against this processed corpus. This does not turn synthetic dev labels or simulated outcomes into real-world labels.

## 5. Labels and development set

`evals/datasets/kaggle_2024_v1/dev_<persona>.json` contains synthetic examples (200 per persona). Gold labels are generated from generator tags/rules, not human annotations or Kaggle labels. Scam/injection examples use seeded and held-out templates; report those slices separately. The current pipeline does **not** import or train on the fake-job labels from the sixth candidate. Evaluation against this dev set is not a real-post quality evaluation.

## 6. Limitations

- Real Upwork job posts are ingested, but Kaggle provides no outcome or GigBid gold labels. Existing reported metrics are synthetic/rule-derived or toy-sample results, not measured marketplace behavior.
- Kaggle page descriptions and license labels do not establish file schema, data quality, representativeness, upstream ownership, or platform permission. Files and rights must be inspected before use.
- Kaggle-described scraped posts may be stale, duplicated, selectively collected, or subject to source-platform restrictions. Upwork-only sources are not representative of the whole freelance market.
- Contract data is selected on completed contracts; it cannot directly describe all postings, bids, unsuccessful applicants, or causal pricing effects. The metadata reviewed does not establish that the source platform is Upwork.
- The freelancer success dataset is tagged synthetic, despite “realistic” wording. It cannot validate real freelancer earnings or churn.
- Unknown-license fake-job data is excluded. If later licensed, global fake-job labels may not match Upwork-specific scams, GigBid's warning signals, or the generated injection labels.
- Circularity: generator, gold rules, and system were authored together; high synthetic decision scores are not evidence of real-world quality.
- Synthetic proposal outcomes reward formula-defined personalization/evidence links. Outcome-aware gains partly learn that formula.
- `LocalSimAdapter` and the heuristic LLM test double are rule-based; reply/hire metrics compare configurations against those rules, not marketplace behavior or a real model.
- Skill extraction and language filtering are noisy; hourly and fixed budgets are not directly comparable; unknown currency, thin category samples, near-duplicate leakage, and market/time/geographic shifts can bias price estimates.
- The instructor's GigSim and hidden test set were not available.

## 7. Reproduce

User-added portfolio evidence now has a separate authenticated ingestion path, documented in [PORTFOLIO_INGESTION.md](PORTFOLIO_INGESTION.md). It preserves source attribution, user-reported outcomes and explicit synthetic provenance on every chunk, stores personal content encrypted, and does not alter this versioned Kaggle corpus or its evaluation gold labels.

The R&D B synthetic evaluation design and results are documented in [RD_B_PREREGISTRATION.md](RD_B_PREREGISTRATION.md) and [RD_B_ABLATION_RESULTS.md](RD_B_ABLATION_RESULTS.md). From the repository root, `python -m evals.rd_b.run_ablation` reruns the frozen retrieval conditions and `python -m evals.rd_b.report_ablation` regenerates their tables. These commands do not make the synthetic labels or simulator outcomes real-world observations.

The supported end-to-end commands are `python -m scripts.prepare_dataset` followed by `python -m scripts.prepare_dataset --verify`.
Download the original [Kaggle version 1 archive](https://www.kaggle.com/datasets/asaniczka/upwork-job-postings-dataset-2024-50k-records?datasetVersionNumber=1)
to `data/raw/upwork-job-postings-2024-v1.zip` first. The preparation script checks the SHA-256 above and retained-row counts, then builds with seed 7.
The verification command re-ingests and rebuilds in a temporary directory and compares all generated corpus/dev files. JSON objects are compared by content because category key order can vary across processes; each manifest's file hashes are independently checked. Python version metadata may differ.
Run `python -m scripts.run_dataset --check` to verify marketplace and portfolio loading, or `python -m scripts.run_dataset` to start the API on that corpus.
These commands work from the repository root in PowerShell or a POSIX shell; a fresh checkout needs dependencies installed and the archive downloaded separately.
See [DATASET_SUBMISSION.md](DATASET_SUBMISSION.md) for the report-ready dataset summary. The lower-level commands remain available:

```bash
python -m dataprep.build_corpus
# The downloaded archive is git-ignored; use the recorded Kaggle v1 source mapping:
python -m dataprep.ingest inspect data/raw/upwork-job-postings-2024-v1.zip --mapping dataprep/mappings/upwork_2024_50k.yaml
python -m dataprep.ingest ingest data/raw/upwork-job-postings-2024-v1.zip --mapping dataprep/mappings/upwork_2024_50k.yaml --out data/processed/real_jobs.jsonl
python -m dataprep.build_corpus --real data/processed/real_jobs.jsonl --out data/processed/kaggle_2024_v1 --dev-out evals/datasets/kaggle_2024_v1
```
