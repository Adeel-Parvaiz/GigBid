"""After a submit: feed the user's edits to style memory. Memory decides via explicit promotion rules."""
from __future__ import annotations

from agent.deps import Deps


def make(deps: Deps):
    async def learn(state):
        edits = state.get("edit_history") or []
        promoted: list[str] = []
        if deps.memory and edits:
            promoted = await deps.memory.observe_edit(
                state["profile"]["freelancer_id"], state["job_id"], edits[0]["original"], edits[-1]["edited"]
            )
        return {"verification_stats": {**state.get("verification_stats", {}), "style_promoted": promoted}}
    return learn
