from __future__ import annotations

from agent.deps import Deps
from agent.marketplace_port import MarketplaceError


def make(deps: Deps):
    async def load_job(state):
        try:
            job = await deps.port.get_job(state["job_id"])
            client = await deps.port.get_client_history(job.get("client_id", ""))
        except MarketplaceError as e:
            if e.code == "rate_limited":
                raise
            return {"status": "error", "errors": [str(e)]}
        return {"job": job, "client": client}
    return load_job
