"""Real job-post ingestion from Kaggle CSVs you download yourself.

  python -m dataprep.ingest inspect path/to/file.csv          # show columns, sample rows, auto-detected mapping
  python -m dataprep.ingest ingest a.csv b.csv --out data/processed/real_jobs.jsonl --limit 20000

Every output record carries provenance="real" and lists which fields were NOT in the source (completed synthetically later).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import chain
from pathlib import Path
from zipfile import ZipFile

import yaml

from dataprep.clean import (
    ascii_ratio,
    clean_text,
    looks_english,
    norm_key,
    parse_money,
    redact_contacts,
    truthy,
)

HERE = Path(__file__).parent
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def _norm(c: str) -> str:
    return re.sub(r"[^a-z0-9]", "", c.lower())


def load_mapping(path: Path | None = None) -> dict[str, list[str]]:
    return yaml.safe_load((path or HERE / "mappings" / "upwork_generic.yaml").read_text())


def detect_mapping(columns: list[str], candidates: dict[str, list[str]]) -> dict[str, str | None]:
    by_norm = {_norm(c): c for c in columns}
    return {field: next((by_norm[_norm(x)] for x in names if _norm(x) in by_norm), None) for field, names in candidates.items()}


@contextmanager
def _csv_file(path: Path):
    if path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            csv_files = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(csv_files) != 1:
                raise ValueError(f"{path}: expected exactly one CSV in ZIP, found {len(csv_files)}")
            with archive.open(csv_files[0]) as raw, io.TextIOWrapper(
                raw, encoding="utf-8-sig", errors="replace", newline=""
            ) as f:
                yield f
        return
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        yield f


class SkillExtractor:
    def __init__(self, path: Path | None = None):
        self.skills = yaml.safe_load((path or HERE / "skills.yaml").read_text())["skills"]
        self.rx = {s["name"]: re.compile(r"(?<![\w+#.])(?:" + "|".join(re.escape(a) for a in s["aliases"]) + r")(?![\w+#])", re.I)
                   for s in self.skills}
        self.cat = {s["name"]: s["category"] for s in self.skills}

    def extract(self, text: str) -> list[str]:
        return [n for n, rx in self.rx.items() if rx.search(text)]

    def category(self, skills: list[str]) -> str:
        c = Counter(self.cat[s] for s in skills if self.cat[s] != "common")
        return c.most_common(1)[0][0] if c else "other"


def read_rows(path: Path, limit: int | None = None) -> Iterator[dict]:
    with _csv_file(path) as f:
        for i, row in enumerate(csv.DictReader(f)):
            if limit is not None and i >= limit:
                return
            yield row


def to_job(row: dict, mp: dict[str, str | None], src: str, ex: SkillExtractor, min_desc: int = 60) -> tuple[dict | None, str]:
    g = lambda k: row.get(mp[k]) if mp.get(k) else None  # noqa: E731
    title = redact_contacts(clean_text(g("title")))
    desc = redact_contacts(clean_text(g("description")))
    if len(desc) < min_desc or not title:
        return None, "too_short_or_untitled"
    if ascii_ratio(title + desc) < 0.9 or not looks_english(desc):
        return None, "non_english"
    hourly = truthy(g("is_hourly")) if mp.get("is_hourly") else None
    lo, hi, fixed = parse_money(g("hourly_low")), parse_money(g("hourly_high")), parse_money(g("budget"))
    if hourly is None:
        hourly = bool(lo or hi) and not fixed
    if hourly and (lo or hi):
        budget = {"min": lo or hi, "max": hi or lo, "currency": "USD", "unit": "hour"}
    elif fixed:
        budget = {"min": fixed, "max": fixed, "currency": "USD", "unit": "project"}
    else:
        budget = {"min": 0, "max": 0, "currency": "USD", "unit": "project"}     # genuinely unknown: kept, flagged by risk rules
    skills = ex.extract(f"{title}. {desc}")
    h = hashlib.sha1(norm_key(title, desc).encode()).hexdigest()[:10]
    return {"job_id": f"real-{h}", "title": title, "description": desc, "required_skills": skills, "budget": budget,
            "category": ex.category(skills), "country": clean_text(g("country")) or None, "published_date": clean_text(g("published")) or None,
            "source_dataset": src, "provenance": "real",
            "synthetic_fields": ["client_id", "duration_days", "screening_questions", "connects_cost", "warning_signals"]}, "ok"


def ingest(paths: list[Path], limit: int | None = None, mapping_file: Path | None = None) -> tuple[list[dict], dict]:
    cands, ex, seen, jobs = load_mapping(mapping_file), SkillExtractor(), set(), []
    stats: Counter = Counter()
    for p in paths:
        rows = read_rows(p, limit)
        first = next(rows, None)
        if first is None:
            stats[f"{p.name}:empty"] += 1
            continue
        mp = detect_mapping(list(first.keys()), cands)
        missing = [k for k in ("title", "description") if not mp[k]]
        if missing:
            raise SystemExit(f"{p.name}: cannot map {missing}. Columns are {list(first.keys())}; run `inspect` and edit the mapping YAML.")
        stats[f"{p.name}:mapping"] = json.dumps(mp)  # type: ignore[assignment]
        for row in chain((first,), rows):
            stats["read"] += 1
            job, why = to_job(row, mp, p.name, ex)
            if job is None:
                stats[f"dropped_{why}"] += 1
                continue
            k = norm_key(job["title"], job["description"])
            if k in seen:
                stats["dropped_duplicate"] += 1
                continue
            seen.add(k)
            jobs.append(job)
            stats["kept"] += 1
    return jobs, dict(stats)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect")
    i.add_argument("csv")
    i.add_argument("--mapping")
    g = sub.add_parser("ingest")
    g.add_argument("csv", nargs="+")
    g.add_argument("--out", default="data/processed/real_jobs.jsonl")
    g.add_argument("--limit", type=int)
    g.add_argument("--mapping")
    a = ap.parse_args()
    if a.cmd == "inspect":
        rows = list(read_rows(Path(a.csv), 3))
        if not rows:
            print("No data rows found.")
            return
        candidates = load_mapping(Path(a.mapping) if a.mapping else None)
        print("columns:", list(rows[0].keys()))
        print("auto-detected mapping:", json.dumps(detect_mapping(list(rows[0].keys()), candidates), indent=1))
        for r in rows[:2]:
            print({k: (redact_contacts(str(v))[:80] + "…" if len(str(v)) > 80 else redact_contacts(str(v)))
                   for k, v in r.items()})
        return
    jobs, stats = ingest([Path(p) for p in a.csv], a.limit, Path(a.mapping) if a.mapping else None)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(j) for j in jobs))
    out.with_suffix(".stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
