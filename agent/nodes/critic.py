from __future__ import annotations

import re

from agent.deps import Deps
from agent.handoffs import Critique, JobSpec, ProposalDraft


def make(deps: Deps):
    async def critic(state):
        draft = ProposalDraft.model_validate(state["proposal_draft"])
        spec = JobSpec.model_validate(state["job_spec"])
        c = await deps.llm.structured("critic", Critique, {
            "draft": draft, "job_spec": spec, "criteria": deps.cfg["critic"]})
        text = draft.cover_letter
        words, criteria = len(text.split()), deps.cfg["critic"]
        issues = list(c.issues)
        if words < criteria["min_words"]:
            issues.append(f"too_short ({words} words)")
        if words > criteria["max_words"]:
            issues.append(f"too_long ({words} words)")
        if re.search(criteria["generic_openers"], text.strip()):
            issues.append("generic_opening")
        c = c.model_copy(update={"passed": c.passed and not issues, "issues": sorted(set(issues))})
        return {"critique": c}
    return critic
