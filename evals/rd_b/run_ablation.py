"""Run the preregistered one-component-at-a-time R&D B retrieval ablation."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.config import load_config
from agent.nodes.fit_matcher import requirements_of
from agent.runtime import load_sample_profile
from evals.metrics import mrr, ndcg_at_k, recall_at_k
from evals.rd_b.ablation_variants import CONDITIONS, build_condition_retrievers
from rag.index.bm25 import BM25Index
from rag.index.vector import DenseIndex, FastEmbedder
from rag.retriever import make_reranker
from rag.variants.v0_naive import RetrievalQuery, chunk_items

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data" / "processed" / "kaggle_2024_v1"
DEFAULT_DEV = ROOT / "evals" / "datasets" / "kaggle_2024_v1"
DEFAULT_OUTPUT = ROOT / "evals" / "rd_b" / "results"
PERSONAS = ("ai-ml-engineer", "fullstack-dev", "data-analyst")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _job_type(case: dict[str, Any], job: dict[str, Any]) -> str:
    labels = job.get("label") or {}
    scam = case.get("scam", labels.get("scam", False))
    injection = case.get("injection", labels.get("injection", False))
    if scam:
        return "scam"
    if injection:
        return "injection"
    return "normal"


def _load_cases(dev_dir: Path) -> dict[str, list[dict[str, Any]]]:
    cases_by_persona = {}
    for persona in PERSONAS:
        path = dev_dir / f"dev_{persona}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        cases = data.get("jobs")
        if not isinstance(cases, list) or not cases:
            raise ValueError(f"{path} must contain a non-empty jobs array")
        if len({case.get("job_id") for case in cases}) != len(cases):
            raise ValueError(f"{path} contains duplicate job IDs")
        if any(not isinstance(case.get("gold_evidence"), list) for case in cases):
            raise ValueError(f"{path} has a case without a gold_evidence list")
        cases_by_persona[persona] = cases
    return cases_by_persona


async def run(
    data_dir: Path = DEFAULT_DATA,
    dev_dir: Path = DEFAULT_DEV,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    data_dir, dev_dir, output_dir = data_dir.resolve(), dev_dir.resolve(), output_dir.resolve()
    manifest_path = data_dir / "DATA_MANIFEST.json"
    items_path = data_dir / "portfolio_items.json"
    jobs_path = data_dir / "jobs.json"
    for path in (manifest_path, items_path, jobs_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required R&D B input not found: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = json.loads(items_path.read_text(encoding="utf-8"))
    jobs = {job["job_id"]: job for job in json.loads(jobs_path.read_text(encoding="utf-8"))}
    cases_by_persona = _load_cases(dev_dir)
    missing_jobs = {
        case["job_id"]
        for cases in cases_by_persona.values()
        for case in cases
        if case["job_id"] not in jobs
    }
    if missing_jobs:
        raise ValueError(f"Development jobs missing from corpus: {sorted(missing_jobs)[:5]}")

    overrides = {
        "rag": {
            "embedder": "fastembed",
            "reranker": "fastembed",
            "cache_dir": str(ROOT / ".local-models" / "rag-cache"),
        }
    }
    cfg = load_config(overrides=overrides)
    rag = cfg["rag"]
    chunks = chunk_items(items, rag.get("chunk_size", 1200), rag.get("chunk_overlap", 150))
    embedder = FastEmbedder(
        rag["fastembed_model"],
        rag.get("fastembed_batch_size", 32),
        rag.get("cache_dir"),
        rag.get("model_threads", 2),
    )
    index = DenseIndex(chunks, embedder)
    bm25 = BM25Index(chunks)
    reranker = make_reranker(cfg)
    retrievers = build_condition_retrievers(index, bm25, reranker)
    rows = []

    for condition in CONDITIONS:
        retrieve = retrievers[condition.name]
        for persona, cases in cases_by_persona.items():
            freelancer_id = load_sample_profile(persona, data_dir)["freelancer_id"]
            for case in cases:
                job = jobs[case["job_id"]]
                query = RetrievalQuery(
                    job_text=f"{job['title']}. {job['description']}",
                    requirements=requirements_of(job),
                    filters={"freelancer_id": freelancer_id},
                )
                started = time.perf_counter()
                hits = await retrieve(query, 10)
                elapsed_ms = (time.perf_counter() - started) * 1000
                ranked_sources = list(dict.fromkeys(
                    hit.get("parent_evidence_id", hit["evidence_id"]) for hit in hits
                ))
                gold = sorted(set(case["gold_evidence"]))
                rows.append({
                    "condition": condition.name,
                    "persona": persona,
                    "job_id": case["job_id"],
                    "job_category": job.get("category") or "unknown",
                    "job_type": _job_type(case, job),
                    "n_requirements": len(query.requirements),
                    "n_gold_sources": len(gold),
                    "gold_source_ids": gold,
                    "ranked_source_ids": ranked_sources,
                    "returned_sources_at_10": len(ranked_sources),
                    "empty_result": not ranked_sources,
                    "recall@5": recall_at_k(ranked_sources, set(gold), 5) if gold else None,
                    "mrr": mrr(ranked_sources, set(gold)) if gold else None,
                    "ndcg@10": ndcg_at_k(ranked_sources, set(gold), 10) if gold else None,
                    "latency_ms": round(elapsed_ms, 4),
                })
        print(f"{condition.name}: completed", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / "ablation_per_job.jsonl"
    _write_jsonl(rows_path, rows)

    def relative_or_absolute(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    result = {
        "experiment": "R&D B preregistered one-component-at-a-time ablation",
        "created_at": datetime.now(UTC).isoformat(),
        "preregistration": "docs/RD_B_PREREGISTRATION.md",
        "seed": 4016,
        "evaluation_status": "synthetic_data_only",
        "statistical_significance_claimed": False,
        "dataset": {
            "data_dir": relative_or_absolute(data_dir),
            "dev_dir": relative_or_absolute(dev_dir),
            "manifest_seed": manifest.get("seed"),
            "manifest_sha256": _sha256(manifest_path),
            "personas": {name: len(cases) for name, cases in cases_by_persona.items()},
            "total_job_persona_rows_per_condition": sum(map(len, cases_by_persona.values())),
            "positive_gold_rows_per_condition": sum(
                bool(case["gold_evidence"])
                for cases in cases_by_persona.values()
                for case in cases
            ),
            "files_sha256": {
                relative_or_absolute(path): _sha256(path)
                for path in [
                    items_path,
                    jobs_path,
                    *(dev_dir / f"dev_{persona}.json" for persona in PERSONAS),
                ]
            },
        },
        "experiment_code_sha256": {
            relative_or_absolute(path): _sha256(path)
            for path in [
                ROOT / "evals" / "rd_b" / "ablation_variants.py",
                ROOT / "evals" / "rd_b" / "run_ablation.py",
                ROOT / "docs" / "RD_B_PREREGISTRATION.md",
            ]
        },
        "configuration": {
            "conditions": [
                {
                    "name": item.name,
                    "decomposition": item.decomposition,
                    "hybrid_bm25_dense": item.hybrid,
                    "cross_encoder_reranking": item.reranking,
                }
                for item in CONDITIONS
            ],
            "embedding": embedder.metadata,
            "reranker": getattr(reranker, "metadata", {"type": type(reranker).__name__}),
            "index": "DenseIndex cosine + in-memory BM25; fixed chunks shared by all conditions",
            "k": 10,
            "source_level_metrics": True,
            "retrieval_only": True,
        },
        "results_file": relative_or_absolute(rows_path),
        "limitations": [
            "Synthetic rule-derived evidence gold and synthetic portfolios only.",
            "No-gold scam/injection rows are reported by returned-evidence rate; Recall@5 is undefined for them.",
            "The preregistration followed inspection of earlier exploratory results; this rerun is not an independent replication.",
            "No decisions, proposals, simulator replies, or real marketplace outcomes were generated by this retrieval run.",
        ],
    }
    summary_path = output_dir / "ablation_run.json"
    summary_path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--dev-dir", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = asyncio.run(run(args.data_dir, args.dev_dir, args.output_dir))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
