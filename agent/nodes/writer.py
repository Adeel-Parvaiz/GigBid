from __future__ import annotations

from agent.deps import Deps
from agent.handoffs import Critique, FitReport, JobSpec, ProposalDraft


def make(deps: Deps):
    async def writer(state):
        crit = state.get("critique")
        crit = Critique.model_validate(crit) if crit is not None else None
        spec = JobSpec.model_validate(state["job_spec"])
        fit = FitReport.model_validate(state["fit_report"])
        revising = crit is not None and not crit.passed
        style_rules = state.get("profile", {}).get("style_rules", [])
        if deps.memory:
            style_rules = style_rules + await deps.memory.style_rules(state["profile"]["freelancer_id"])
        draft = await deps.llm.structured("writer", ProposalDraft, {
            "job": state["job"], "job_spec": spec, "fit_report": fit,
            "evidence": state["evidence"], "critique": crit if revising else None,
            "style_rules": style_rules})
        draft = draft.model_copy(update={"job_id": spec.job_id,
                                         "questions": spec.screening_questions,
                                         "claims": [c for c in draft.claims if c.kind != "logistics"]})
        return {"proposal_draft": draft,
                "revisions": state.get("revisions", 0) + (1 if revising else 0)}
    return writer
