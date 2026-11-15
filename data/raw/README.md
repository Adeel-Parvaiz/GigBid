# Raw Kaggle datasets

Raw dataset archives are git-ignored and must not be committed or redistributed by default.

## Ingested source

- Author/title: asaniczka, *Upwork Job Postings Dataset 2024 (50K Records)*
- URL: https://www.kaggle.com/datasets/asaniczka/upwork-job-postings-dataset-2024-50k-records
- Kaggle version: 1; Kaggle-displayed license: ODC Attribution License (ODC-By)
- Accessed/downloaded: 2026-11-11
- Archive: `upwork-job-postings-2024-v1.zip` (contains `upwork-jobs.csv`)
- SHA-256: `3f40f06c267f6429e6c9fdd9a81c0c9bb3a3c9eb85edadb1d6638394e9ce5b35`

Kaggle's displayed license does not establish rights to the upstream marketplace data. See [the data card](../../docs/DATA_CARD.md) for attribution, source/platform caveats, preprocessing, and limitations.

Inspect and ingest without extracting the archive:

```bash
python -m dataprep.ingest inspect data/raw/upwork-job-postings-2024-v1.zip --mapping dataprep/mappings/upwork_2024_50k.yaml
python -m dataprep.ingest ingest data/raw/upwork-job-postings-2024-v1.zip --mapping dataprep/mappings/upwork_2024_50k.yaml --out data/processed/real_jobs.jsonl
python -m dataprep.build_corpus --real data/processed/real_jobs.jsonl --out data/processed/kaggle_2024_v1 --dev-out evals/datasets/kaggle_2024_v1
```
