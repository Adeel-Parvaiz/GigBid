"""Local fixture API for adapter tests. Not an implementation of instructor GigSim."""
from fastapi import FastAPI, Header, HTTPException

from mcp_servers.marketplace.adapters.sample import SampleAdapter


def create_app():
    app, adapter = FastAPI(), SampleAdapter()

    @app.middleware("http")
    async def auth(request, next_handler):
        from fastapi.responses import JSONResponse
        if request.headers.get("Authorization") != "Bearer fixture-upstream":
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await next_handler(request)

    @app.get("/fixture/jobs")
    async def jobs(q: str | None = None, limit: int = 20):
        return {"jobs": await adapter.search_jobs(q, limit)}

    @app.get("/fixture/jobs/{job_id}")
    async def job(job_id: str):
        return await adapter.get_job(job_id)

    @app.get("/fixture/clients/{client_id}")
    async def client(client_id: str):
        return await adapter.get_client_history(client_id)

    @app.get("/fixture/balance")
    async def balance():
        return await adapter.get_connects_balance()

    @app.post("/fixture/drafts")
    async def draft(body: dict, idempotency_key: str = Header()):
        if idempotency_key != body["key"]:
            raise HTTPException(400, "key mismatch")
        return await adapter.create_proposal_draft(body["proposal"], body["key"], body["preview"])

    @app.post("/fixture/drafts/{draft_id}/submit")
    async def submit(draft_id: str, body: dict):
        return await adapter.submit_proposal(draft_id, body["key"])

    @app.get("/fixture/threads")
    async def threads():
        return {"threads": await adapter.list_threads()}

    @app.get("/fixture/threads/{thread_id}")
    async def messages(thread_id: str):
        return await adapter.list_messages(thread_id)

    @app.post("/fixture/threads/{thread_id}/messages")
    async def send(thread_id: str, body: dict):
        return await adapter.send_message(thread_id, body["text"], body["key"])

    @app.get("/fixture/counters")
    async def counters():
        return {"balance": adapter.balance, "drafts": len(adapter.drafts), "submissions": len(adapter.submissions), "sent": len(adapter.sent)}

    return app
