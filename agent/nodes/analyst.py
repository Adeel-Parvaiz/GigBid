from __future__ import annotations

from agent.deps import Deps
from agent.handoffs import JobSpec


def make(deps: Deps):
    async def analyst(state):
        spec = await deps.llm.structured("analyst", JobSpec, {"job": state["job"]})
        return {"job_spec": spec}
    return analyst
