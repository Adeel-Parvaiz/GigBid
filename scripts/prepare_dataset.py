"""Rebuild the selected Kaggle corpus, or verify it without modifying existing outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from dataprep.build_corpus import build
from dataprep.ingest import ingest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/raw/upwork-job-postings-2024-v1.zip"
CHECKSUM = "3f40f06c267f6429e6c9fdd9a81c0c9bb3a3c9eb85edadb1d6638394e9ce5b35"
CORPUS = ROOT / "data/processed/kaggle_2024_v1"
DEV = ROOT / "evals/datasets/kaggle_2024_v1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Rebuild in a temporary directory and compare every corpus/dev file")
    args = parser.parse_args()
    if not ARCHIVE.exists():
        raise SystemExit(f"Download Kaggle dataset version 1 as {ARCHIVE}. See docs/DATA_CARD.md section 7.")
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != CHECKSUM:
        raise SystemExit("Archive checksum differs from the documented version 1 source; refusing to build.")
    print("Archive checksum verified. Ingesting 53,058 source rows; this can take several minutes.", flush=True)
    jobs, stats = ingest([ARCHIVE], mapping_file=ROOT / "dataprep/mappings/upwork_2024_50k.yaml")
    if (stats["read"], stats["kept"]) != (53058, 49699):
        raise SystemExit(f"Ingestion counts changed: {stats}")
    with tempfile.TemporaryDirectory(prefix="gigbid-dataset-") as temporary:
        base = Path(temporary)
        out, dev = (base / "corpus", base / "dev") if args.verify else (CORPUS, DEV)
        manifest = build(out, dev, jobs, seed=7)
        if args.verify:
            failures = []
            for generated, existing in ((out, CORPUS), (dev, DEV)):
                for file in generated.iterdir():
                    target = existing / file.name
                    if not target.exists():
                        failures.append(str(target))
                        continue
                    if file.name == "DATA_MANIFEST.json":
                        left, right = json.loads(file.read_text()), json.loads(target.read_text())
                        for record, directory in ((left, generated), (right, existing)):
                            for name, expected in record.pop("files").items():
                                content = directory / name
                                if not content.exists() or hashlib.sha256(content.read_bytes()).hexdigest()[:16] != expected:
                                    failures.append(f"Manifest hash mismatch: {content}")
                            record.pop("python", None)
                        equal = left == right
                    elif file.suffix == ".json":
                        # Category dictionaries use set iteration; JSON key order has no semantic meaning.
                        equal = json.loads(file.read_text()) == json.loads(target.read_text())
                    else:
                        equal = file.read_bytes() == target.read_bytes()
                    if not equal:
                        failures.append(str(target))
            if failures:
                raise SystemExit("Reproduction mismatch:\n" + "\n".join(failures))
        else:
            processed = ROOT / "data/processed"
            (processed / "real_jobs.jsonl").write_text("\n".join(json.dumps(j) for j in jobs))
            (processed / "real_jobs.stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps({"status": "verified" if args.verify else "built", "archive_sha256": CHECKSUM,
                      "source_rows": stats["read"], "retained_rows": stats["kept"],
                      "real_jobs_used": manifest["real_jobs_used"], "sizes": manifest["sizes"]}, indent=2))


if __name__ == "__main__":
    main()
