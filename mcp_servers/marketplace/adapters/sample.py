"""Local stand-in marketplace for development. Implements MarketplacePort (agent/marketplace_port.py).

Not GigSim. When the real GigSim docs are available, write gigsim.py next to this file; the
graph never knows which adapter it talks to.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent.marketplace_port import MarketplaceError

DATA = Path(os.environ.get("GIGBID_DATA_DIR") or Path(__file__).resolve().parents[3] / "data" / "sample")


class SampleAdapter:
    def __init__(self, data_dir: Path = DATA, connects: int = 100):
        self._jobs = {j["job_id"]: j for j in json.loads((data_dir / "jobs.json").read_text())}
        self._clients = {c["client_id"]: c for c in json.loads((data_dir / "clients.json").read_text())}
        self.balance = connects
        mf = data_dir / "messages.json"
        self._threads = {t["thread_id"]: t for t in json.loads(mf.read_text())} if mf.exists() else {}
        self.sent: dict[str, dict] = {}           # idempotency key -> sent message
        self.drafts: dict[str, dict] = {}        # idempotency key -> draft record
        self.submissions: dict[str, dict] = {}   # idempotency key -> submission record
        self.audit: list[dict] = []              # append-only

    def _log(self, tool: str, **kw: Any) -> None:
        self.audit.append({"tool": tool, **kw})

    @staticmethod
    def _agent_view(job: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in job.items() if key != "label"}

    async def search_jobs(self, query: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        self._log("search_jobs", query=query)
        jobs = list(self._jobs.values())
        if query:
            jobs = [j for j in jobs if query.lower() in (j["title"] + j["description"]).lower()]
        return [self._agent_view(j) for j in jobs[:limit]]

    async def get_job(self, job_id: str) -> dict[str, Any]:
        self._log("get_job", job_id=job_id)
        if job_id not in self._jobs:
            raise MarketplaceError("job_not_found", job_id)
        return self._agent_view(self._jobs[job_id])

    async def get_client_history(self, client_id: str) -> dict[str, Any]:
        self._log("get_client_history", client_id=client_id)
        return dict(self._clients.get(client_id, {"client_id": client_id, "completed_projects": 0,
                                                 "average_rating": None, "payment_verified": False}))

    async def get_connects_balance(self) -> dict[str, Any]:
        return {"balance": self.balance}

    async def create_proposal_draft(self, payload, idempotency_key, dry_run=False):
        job = await self.get_job(payload["job_id"])
        cost = job["connects_cost"]
        if dry_run:
            return {"dry_run": True, "would_send": payload, "connects_cost": cost}
        if idempotency_key in self.drafts:
            return {**self.drafts[idempotency_key], "replayed": True}
        rec = {"draft_id": f"draft-{len(self.drafts) + 1:04d}", "status": "draft",
               "payload": payload, "connects_cost": cost}
        self.drafts[idempotency_key] = rec
        self._log("create_proposal_draft", key=idempotency_key, draft_id=rec["draft_id"])
        return {**rec, "replayed": False}

    async def submit_proposal(self, draft_id, idempotency_key):
        if idempotency_key in self.submissions:
            return {**self.submissions[idempotency_key], "replayed": True}
        draft = next((d for d in self.drafts.values() if d["draft_id"] == draft_id), None)
        if draft is None:
            raise MarketplaceError("draft_not_found", draft_id)
        if self.balance < draft["connects_cost"]:
            raise MarketplaceError("insufficient_connects")
        self.balance -= draft["connects_cost"]
        rec = {"draft_id": draft_id, "status": "submitted", "connects_spent": draft["connects_cost"]}
        self.submissions[idempotency_key] = rec
        self._log("submit_proposal", key=idempotency_key, draft_id=draft_id)
        return {**rec, "replayed": False}

    async def list_threads(self) -> list[dict[str, Any]]:
        self._log("list_threads")
        return [{"thread_id": t["thread_id"], "job_id": t["job_id"], "client_id": t["client_id"],
                 "last_message": t["messages"][-1]["text"], "last_from": t["messages"][-1]["from"]}
                for t in self._threads.values()]

    async def list_messages(self, thread_id: str) -> dict[str, Any]:
        self._log("list_messages", thread_id=thread_id)
        if thread_id not in self._threads:
            raise MarketplaceError("thread_not_found", thread_id)
        t = self._threads[thread_id]
        return {**t, "messages": [dict(m) for m in t["messages"]]}

    async def send_message(self, thread_id: str, text: str, idempotency_key: str) -> dict[str, Any]:
        if idempotency_key in self.sent:
            return {**self.sent[idempotency_key], "replayed": True}
        if thread_id not in self._threads:
            raise MarketplaceError("thread_not_found", thread_id)
        t = self._threads[thread_id]
        msg = {"id": f"m{len(t['messages']) + 1}", "from": "freelancer", "text": text, "ts": "now"}
        t["messages"].append(msg)
        rec = {"message_id": msg["id"], "thread_id": thread_id}
        self.sent[idempotency_key] = rec
        self._log("send_message", key=idempotency_key, thread_id=thread_id)
        return {**rec, "replayed": False}
