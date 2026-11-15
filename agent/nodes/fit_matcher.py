"""Fit Matcher: map each requirement to portfolio evidence. Runs in parallel with Analyst, so it
works from the raw job (not JobSpec)."""
from __future__ import annotations

import asyncio
import re

from agent.deps import Deps
from agent.handoffs import FitReport, RequirementEvidence
from rag.retriever import RetrievalQuery


def _matches_requirement(requirement: str, hit: dict) -> bool:
    text = " ".join((hit.get("title", ""), hit.get("summary", ""), " ".join(hit.get("skills", [])))).lower()
    if requirement.lower() in text:
        return True
    required_terms = set(re.findall(r"[a-z0-9+#.]+", requirement.lower()))
    evidence_terms = set(re.findall(r"[a-z0-9+#.]+", text))
    return bool(required_terms) and len(required_terms & evidence_terms) / len(required_terms) >= 0.7


def requirements_of(job: dict) -> list[str]:
    if job.get("required_skills"):
        return list(job["required_skills"])
    return [s for s in re.split(r"(?<=[.!?])\s+", job.get("description", "")) if s]


def make(deps: Deps):
    async def fit_matcher(state):
        job, pid = state["job"], state["profile"]["freelancer_id"]
        reqs = requirements_of(job)
        q = RetrievalQuery(job_text=f"{job['title']}. {job['description']}", requirements=reqs,
                           filters={"freelancer_id": pid})
        k = deps.cfg["rag"]["k"]
        hits = await deps.retriever.retrieve(q, k)
        per_requirement = await asyncio.gather(*(
            deps.retriever.retrieve(
                RetrievalQuery(job_text=f"{job['title']}. {requirement}", requirements=[requirement],
                               filters={"freelancer_id": pid}),
                min(2, k),
            )
            for requirement in reqs
        ))
        evidence_by_id = {hit["evidence_id"]: hit for hit in hits}
        requirement_evidence = []
        for requirement, candidates in zip(reqs, per_requirement, strict=True):
            for hit in candidates:
                evidence_by_id.setdefault(hit["evidence_id"], hit)
            requirement_evidence.append(RequirementEvidence(
                requirement=requirement,
                evidence_ids=[hit["evidence_id"] for hit in candidates],
                matched=any(_matches_requirement(requirement, hit) for hit in candidates),
            ))
        matched = [item.requirement for item in requirement_evidence if item.matched]
        missing = [r for r in reqs if r not in matched]
        report = FitReport(score=len(matched) / len(reqs) if reqs else 0.0, matched_skills=matched,
                           missing_skills=missing, evidence_ids=list(evidence_by_id),
                           requirement_evidence=requirement_evidence,
                           variant=deps.retriever.variant)
        return {"fit_report": report, "evidence": list(evidence_by_id.values())}
    return fit_matcher
