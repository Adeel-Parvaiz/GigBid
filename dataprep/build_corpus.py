"""Build the processed corpus: python -m dataprep.build_corpus [--real data/processed/real_jobs.jsonl] [--out data/processed] [--seed 7]"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import statistics
from collections import Counter
from pathlib import Path

from dataprep import synth

ROOT = Path(__file__).resolve().parents[1]


def market_stats(jobs: list[dict]) -> dict:
    out: dict = {}
    for cat in {j.get("category", "other") for j in jobs}:
        row = {}
        for kind, sel in (("fixed", lambda j: j["budget"]["unit"] == "project"), ("hourly", lambda j: j["budget"]["unit"] == "hour")):
            vals = [((j["budget"]["min"] + j["budget"]["max"]) / 2) for j in jobs if j.get("category", "other") == cat and sel(j) and j["budget"]["max"]]
            if len(vals) >= 5:
                q = statistics.quantiles(vals, n=4)
                row[kind] = {"p25": round(q[0], 2), "p50": round(q[1], 2), "p75": round(q[2], 2), "n": len(vals)}
        out[cat] = row
    return out


def build(out: Path, dev_dir: Path, real: list[dict] | None = None, seed: int = 7, n_hist: int = 1500, n_stream: int = 1500, n_dev: int = 200, n_clients: int = 400) -> dict:
    rng = random.Random(seed)
    cl = synth.clients(n_clients, rng)
    real = [synth.complete_real_job(j, rng, cl) for j in (real or [])]
    rng.shuffle(real)
    half = len(real) // 2
    hist, stream = real[:half][:n_hist], real[half:][:n_stream]
    hist += synth.synthetic_jobs(max(0, n_hist - len(hist)), rng, cl, 0)
    synthetic_stream = sum(j["provenance"] == "synthetic" for j in stream)
    n_s = max(0, n_stream - synthetic_stream)
    stream += synth.synthetic_jobs(n_s, rng, cl, 100_000)
    stream += synth.scam_and_injection(max(10, n_stream // 16), max(8, n_stream // 25), rng, cl, 200_000)
    dup = []
    for j in rng.sample(stream, k=max(3, n_stream // 40)):
        synthetic_fields = set(j.get("synthetic_fields", []))
        synthetic_fields.add("duplicate_of")
        dup.append({**j, "job_id": j["job_id"] + "-dup", "description": j["description"] + " ",
                    "synthetic_fields": sorted(synthetic_fields),
                    "label": {**j.get("label", {}), "duplicate_of": j["job_id"]}})
    stream += dup
    rng.shuffle(stream)
    market = market_stats(hist)
    people = synth.personas()
    items, props, devs = [], [], {}
    dev_flagged_n = int(n_dev * .2)
    clean = [j for j in stream if not j.get("label", {}).get("duplicate_of") and j["provenance"] == "synthetic"]
    flagged = [j for j in clean if j["label"]["scam"] or j["label"]["injection"]]
    normal = [j for j in clean if not (j["label"]["scam"] or j["label"]["injection"])]
    for p in people:
        pid = p["freelancer_id"]
        its = synth.portfolio(pid, rng)
        items += its
        props += synth.past_proposals(pid, hist, its, rng)
        dom = [j for j in normal if j.get("category") == synth.PERSONAS[pid]["domain"]]
        other = [j for j in normal if j.get("category") != synth.PERSONAS[pid]["domain"]]
        n_domain = int(n_dev * .5)
        n_other = n_dev - dev_flagged_n - n_domain
        if len(flagged) < dev_flagged_n or len(dom) < n_domain or len(other) < n_other:
            raise ValueError(f"Unable to build {n_dev} development jobs for {pid}; generated pools are too small")
        chosen = (rng.sample(flagged, k=dev_flagged_n) + rng.sample(dom, k=n_domain) +
                  rng.sample(other, k=n_other))
        devs[pid] = [synth.gold_for(j, pid, its, market) for j in chosen]
    hidden = synth.hidden_prefs(stream, rng)
    convs = synth.conversations([j for j in stream if not j.get("label", {}).get("duplicate_of")], rng)
    out.mkdir(parents=True, exist_ok=True)
    dev_dir.mkdir(parents=True, exist_ok=True)
    w = lambda name, obj: (out / name).write_text(json.dumps(obj, indent=None, default=str))  # noqa: E731
    w("jobs.json", stream)
    (out / "historical_jobs.jsonl").write_text("\n".join(json.dumps(j) for j in hist))
    w("clients.json", cl)
    w("hidden_prefs.json", hidden)
    w("portfolio_items.json", items)
    w("past_proposals.json", props)
    w("freelancers.json", people)
    w("messages.json", convs)
    w("market_stats.json", market)
    for pid, rows in devs.items():
        (dev_dir / f"dev_{pid}.json").write_text(json.dumps({
            "_note": "Synthetic job text; gold labels derived by rule from generation-time tags; not human-labelled.",
            "provenance_counts": dict(Counter(j["provenance"] for j in rows)),
            "label_provenance": "synthetic_rule",
            "jobs": rows,
        }, indent=1))
    corpus_jobs = stream + hist
    source_jobs = [j for j in corpus_jobs if not j.get("label", {}).get("duplicate_of")]
    prov = Counter(j["provenance"] for j in source_jobs)
    record_prov = Counter(j["provenance"] for j in corpus_jobs)
    source_counts = Counter(j.get("source_dataset", "synthetic_generator") for j in source_jobs)
    manifest = {"seed": seed, "python": platform.python_version(), "provenance_counts_jobs": dict(prov),
                "record_provenance_counts_including_duplicates": dict(record_prov),
                "source_dataset_counts": dict(source_counts),
                "synthetic_duplicate_records": len(dup),
                "sizes": {"historical": len(hist), "stream": len(stream), "clients": len(cl), "portfolio_items": len(items), "past_proposals": len(props),
                          "conversations": len(convs), "dev_per_persona": {k: len(v) for k, v in devs.items()}},
                "dev_provenance_per_persona": {k: dict(Counter(j["provenance"] for j in v)) for k, v in devs.items()},
                "real_jobs_used": sum(j["provenance"] == "real" for j in source_jobs),
                "label_counts_stream": {"scam": sum(bool(j.get("label", {}).get("scam")) for j in stream),
                                        "injection": sum(bool(j.get("label", {}).get("injection")) for j in stream),
                                        "duplicates": len(dup)},
                "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                          for p in sorted(out.glob("*.json*")) if p.name != "DATA_MANIFEST.json"}}
    (out / "DATA_MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real")
    ap.add_argument("--out", default=str(ROOT / "data/processed"))
    ap.add_argument("--dev-out", default=str(ROOT / "evals/datasets"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--hist", type=int, default=1500)
    ap.add_argument("--stream", type=int, default=1500)
    a = ap.parse_args()
    if a.real and not Path(a.real).is_file():
        ap.error(f"Real-job input does not exist: {a.real}; ingest the downloaded source first")
    real = [json.loads(line) for line in Path(a.real).read_text().splitlines() if line] if a.real else []
    print(json.dumps(build(Path(a.out), Path(a.dev_out), real, a.seed, a.hist, a.stream), indent=1))


if __name__ == "__main__":
    main()
