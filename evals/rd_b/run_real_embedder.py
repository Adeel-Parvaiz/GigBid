"""Compare hashing and local FastEmbed retrieval on synthetic GigBid evaluation data.

Run from the repository root:
    python -m evals.rd_b.run_real_embedder

The local open model is downloaded on first use and cached by FastEmbed. The
instructor dataset can be supplied later with --data-dir and --dev-dir.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import random
import time
from pathlib import Path
from typing import Any

import numpy as np
from langgraph.checkpoint.memory import InMemorySaver

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.handoffs import ClaimVerdict
from agent.llm import HeuristicLLM
from agent.nodes.fit_matcher import requirements_of
from agent.runtime import build_deps, load_sample_profile
from evals.metrics import mrr, ndcg_at_k, prf, recall_at_k
from mcp_servers.marketplace.adapters.sample import SampleAdapter
from rag.index.vector import DenseIndex, FastEmbedder, HashingEmbedder
from rag.retriever import VARIANTS, RetrievalQuery, build_retriever

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "data" / "processed" / "kaggle_2024_v1"
DEFAULT_DEV_DIR = ROOT / "evals" / "datasets" / "kaggle_2024_v1"
RESULTS_DIR = Path(__file__).with_name("results")
RETRIEVAL_RESULTS = RESULTS_DIR / "retrieval_per_job.jsonl"
DECISION_RESULTS = RESULTS_DIR / "decision_per_job.jsonl"
AGGREGATE_RESULTS = RESULTS_DIR / "results.json"
DEFAULT_PERSONAS = ("ai-ml-engineer", "fullstack-dev", "data-analyst")
EMBEDDERS = ("hashing", "fastembed")
DECISION_VARIANTS = ("v1_decomposed", "v1_v2_v3")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows),
                    encoding="utf-8")


def _load_dev(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError(f"{path} must contain a non-empty 'jobs' list")
    required = {"job_id", "gold_action", "gold_evidence"}
    for row in jobs:
        if not required <= row.keys() or row["gold_action"] not in {"bid", "skip"}:
            raise ValueError(f"{path} contains an evaluation job with an invalid schema")
        if not isinstance(row["gold_evidence"], list):
            raise ValueError(f"{path} gold_evidence must be a list")
    if len({row["job_id"] for row in jobs}) != len(jobs):
        raise ValueError(f"{path} contains duplicate job IDs")
    return jobs


def _label_counts(rows: list[ClaimVerdict]) -> dict[str, int]:
    return {label: sum(row.label == label for row in rows)
            for label in ("supported", "partly_supported", "unsupported")}


def _classification(predictions: list[bool], labels: list[bool]) -> dict[str, float | int]:
    score = prf(predictions, labels)
    return {
        "n": len(labels),
        "accuracy": sum(p == y for p, y in zip(predictions, labels, strict=True)) / len(labels) if labels else 0.0,
        "precision": score["precision"],
        "recall": score["recall"],
        "f1": score["f1"],
        "confusion": {
            "true_positive": sum(p and y for p, y in zip(predictions, labels, strict=True)),
            "false_positive": sum(p and not y for p, y in zip(predictions, labels, strict=True)),
            "false_negative": sum(not p and y for p, y in zip(predictions, labels, strict=True)),
            "true_negative": sum(not p and not y for p, y in zip(predictions, labels, strict=True)),
        },
    }


def _model_metadata(embedder: Any) -> dict[str, Any]:
    if isinstance(embedder, FastEmbedder):
        return dict(embedder.metadata)
    if isinstance(embedder, HashingEmbedder):
        return {"provider": "in-repo hashing baseline", "model": "HashingEmbedder", "dimensions": embedder.dim}
    raise TypeError(f"Unsupported experiment embedder: {type(embedder).__name__}")


async def _retrieval_trials(
    items: list[dict[str, Any]],
    dense: DenseIndex,
    adapter: SampleAdapter,
    data_dir: Path,
    dev_by_persona: dict[str, list[dict[str, Any]]],
    personas: tuple[str, ...],
    variants: tuple[str, ...],
    embedder_name: str,
    config_overrides: dict | None = None,
) -> list[dict[str, Any]]:
    rows = []
    cfg = load_config(overrides=config_overrides)
    for persona in personas:
        fid = load_sample_profile(persona, data_dir)["freelancer_id"]
        dev = dev_by_persona[persona]
        for variant in variants:
            variant_cfg = {**cfg, "rag": {**cfg["rag"], "variant": variant}}
            retriever = build_retriever(variant_cfg, items, dense_index=dense)
            for case in dev:
                relevant = case["gold_evidence"]
                if not relevant:
                    continue
                job = await adapter.get_job(case["job_id"])
                query = RetrievalQuery(
                    job_text=f"{job['title']}. {job['description']}",
                    requirements=requirements_of(job),
                    filters={"freelancer_id": fid},
                )
                started = time.perf_counter()
                hits = await retriever.retrieve(query, 10)
                elapsed_ms = (time.perf_counter() - started) * 1000
                ranked_ids = [hit["evidence_id"] for hit in hits]
                gold = set(relevant)
                rows.append({
                    "embedder": embedder_name,
                    "persona": persona,
                    "variant": variant,
                    "job_id": case["job_id"],
                    "n_relevant_evidence": len(gold),
                    "relevant_evidence_retrieved_at_5": len(set(ranked_ids[:5]) & gold),
                    "relevant_evidence_retrieved_at_10": len(set(ranked_ids[:10]) & gold),
                    "recall@5": recall_at_k(ranked_ids, gold, 5),
                    "mrr": mrr(ranked_ids, gold),
                    "ndcg@10": ndcg_at_k(ranked_ids, gold, 10),
                    "latency_ms": round(elapsed_ms, 4),
                    "retrieved_ids": ranked_ids,
                    "gold_evidence_ids": sorted(gold),
                })
    return rows

async def _decision_trials(
    data_dir: Path,
    dense: DenseIndex,
    dev_by_persona: dict[str, list[dict[str, Any]]],
    personas: tuple[str, ...],
    embedder_name: str,
    seed: int,
    model_name: str | None,
) -> list[dict[str, Any]]:
    rows = []
    for persona in personas:
        profile = load_sample_profile(persona, data_dir)
        for variant in DECISION_VARIANTS:
            rag_overrides = {"variant": variant, "embedder": embedder_name}
            if model_name and embedder_name == "fastembed":
                rag_overrides["fastembed_model"] = model_name
            cfg = load_config(overrides={"rag": rag_overrides})
            deps = build_deps(cfg, port=SampleAdapter(data_dir), llm=HeuristicLLM(), data_dir=data_dir,
                              dense_index=dense)
            graph = build_bid_graph(deps, InMemorySaver())
            for case in dev_by_persona[persona]:
                started = time.perf_counter()
                out = await graph.ainvoke(
                    {"job_id": case["job_id"], "profile": profile},
                    {"configurable": {"thread_id": f"rd-b-{embedder_name}-{variant}-{persona}-{case['job_id']}"}},
                )
                labels = out.get("claim_verification", [])
                rows.append({
                    "embedder": embedder_name,
                    "variant": variant,
                    "persona": persona,
                    "job_id": case["job_id"],
                    "action": out["decision"].action,
                    "gold_action": case["gold_action"],
                    "decision_correct": out["decision"].action == case["gold_action"],
                    "retrieved_evidence_ids": [e["evidence_id"] for e in out.get("evidence", [])],
                    "claim_verdict_counts": _label_counts(labels),
                    "claim_verdicts": [label.model_dump(mode="json") for label in labels],
                    "latency_ms": round((time.perf_counter() - started) * 1000, 4),
                    "seed": seed,
                })
    return rows


async def run(
    data_dir: Path = DEFAULT_DATA_DIR,
    dev_dir: Path = DEFAULT_DEV_DIR,
    personas: tuple[str, ...] = DEFAULT_PERSONAS,
    variants: tuple[str, ...] = tuple(sorted(VARIANTS)),
    seed: int = 4016,
    model_name: str | None = None,
) -> dict[str, Any]:
    random.seed(seed)
    data_dir, dev_dir = data_dir.resolve(), dev_dir.resolve()
    manifest_path = data_dir / "DATA_MANIFEST.json"
    items_path = data_dir / "portfolio_items.json"
    if not manifest_path.exists() or not items_path.exists():
        raise FileNotFoundError(f"Expected processed corpus and DATA_MANIFEST.json under {data_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = json.loads(items_path.read_text(encoding="utf-8"))
    dev_by_persona = {persona: _load_dev(dev_dir / f"dev_{persona}.json") for persona in personas}
    jobs_index = {job["job_id"] for job in json.loads((data_dir / "jobs.json").read_text(encoding="utf-8"))}
    for persona, cases in dev_by_persona.items():
        missing = {case["job_id"] for case in cases} - jobs_index
        if missing:
            raise ValueError(f"{persona} dev jobs are absent from this corpus: {sorted(missing)[:3]}")
    unknown_variants = set(variants) - set(VARIANTS)
    if unknown_variants:
        raise ValueError(f"Unknown RAG variants: {sorted(unknown_variants)}")

    retrieval_rows, decision_rows, embedding_metadata = [], [], {}
    for embedder_name in EMBEDDERS:
        overrides = {"rag": {"embedder": embedder_name}}
        if model_name and embedder_name == "fastembed":
            overrides["rag"]["fastembed_model"] = model_name
        cfg = load_config(overrides=overrides)
        embedder = HashingEmbedder() if embedder_name == "hashing" else FastEmbedder(
            cfg["rag"]["fastembed_model"], cfg["rag"].get("fastembed_batch_size", 32))
        started = time.perf_counter()
        dense = DenseIndex(items, embedder)
        embedding_ms = (time.perf_counter() - started) * 1000
        vector_path = RESULTS_DIR / f"portfolio_embeddings_{embedder_name}.npz"
        vector_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(vector_path, evidence_ids=np.asarray([item["evidence_id"] for item in items]),
                            embeddings=dense.vecs)
        embedding_metadata[embedder_name] = {
            **_model_metadata(embedder),
            "corpus_items_reembedded": len(items),
            "portfolio_corpus_sha256": _sha256(items_path.read_bytes()),
            "embedding_matrix_sha256": _sha256(dense.vecs.tobytes()),
            "embedding_dimension": int(dense.vecs.shape[1]),
            "index_build_ms": round(embedding_ms, 3),
            "saved_vectors": str(vector_path.relative_to(ROOT)),
            "saved_vectors_sha256": _sha256(vector_path.read_bytes()),
        }
        adapter = SampleAdapter(data_dir)
        retrieval_rows.extend(await _retrieval_trials(
            items, dense, adapter, data_dir, dev_by_persona, personas, variants, embedder_name))
        decision_rows.extend(await _decision_trials(
            data_dir, dense, dev_by_persona, personas, embedder_name, seed,
            cfg["rag"].get("fastembed_model") if embedder_name == "fastembed" else None))

    _jsonl(RETRIEVAL_RESULTS, retrieval_rows)
    _jsonl(DECISION_RESULTS, decision_rows)
    try:
        fastembed_version = importlib.metadata.version("fastembed")
    except importlib.metadata.PackageNotFoundError:
        fastembed_version = None
    try:
        recorded_data_dir = str(data_dir.relative_to(ROOT))
    except ValueError:
        recorded_data_dir = str(data_dir)
    result = {
        "experiment": "R&D B: real local embedding model evaluation",
        "seed": seed,
        "evaluation_status": "synthetic_data_only",
        "instructor_dataset_available": False,
        "marketplace_performance_claimed": False,
        "dataset": {
            "data_dir": recorded_data_dir,
            "manifest_seed": manifest.get("seed"),
            "manifest_sha256": _sha256(manifest_path.read_bytes()),
            "job_provenance_counts": manifest.get("provenance_counts_jobs", {}),
            "dev_jobs_per_persona": {k: len(v) for k, v in dev_by_persona.items()},
            "dev_job_provenance": {
                k: sorted({case.get("provenance", "unspecified") for case in v}) for k, v in dev_by_persona.items()
            },
            "dev_label_provenance": {
                k: sorted({case.get("label_provenance", "unspecified") for case in v}) for k, v in dev_by_persona.items()
            },
            "portfolio_items": len(items),
            "portfolio_provenance": sorted({item.get("provenance", "unspecified") for item in items}),
        },
        "configuration": {
            "fastembed_version": fastembed_version,
            "baseline": "HashingEmbedder, 512 dimensions, in-repo deterministic test baseline",
            "real_embedder": embedding_metadata["fastembed"],
            "embedding_conditions": embedding_metadata,
            "conditions": list(EMBEDDERS),
            "retrieval_variants": list(variants),
            "decision_variants": list(DECISION_VARIANTS),
            "decision_llm": "HeuristicLLM deterministic test double",
            "vector_index": "DenseIndex: in-memory NumPy cosine similarity; not an external vector database",
            "retrieval_k": 10,
            "claim_verification": "existing lexical grounding verifier; no LLM judge",
        },
        "results_files": {
            "retrieval_per_job": str(RETRIEVAL_RESULTS.relative_to(ROOT)),
            "decision_per_job": str(DECISION_RESULTS.relative_to(ROOT)),
        },
        "statistical_significance_claimed": False,
    }
    AGGREGATE_RESULTS.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dev-dir", type=Path, default=DEFAULT_DEV_DIR)
    parser.add_argument("--personas", default=",".join(DEFAULT_PERSONAS))
    parser.add_argument("--variants", default=",".join(sorted(VARIANTS)))
    parser.add_argument("--seed", type=int, default=4016)
    parser.add_argument("--model", help="FastEmbed model name (defaults to agent/config.yaml)")
    args = parser.parse_args()
    result = asyncio.run(run(args.data_dir, args.dev_dir, tuple(args.personas.split(",")),
                             tuple(args.variants.split(",")), args.seed, args.model))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
