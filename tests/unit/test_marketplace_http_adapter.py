import json
from pathlib import Path

import httpx
import pytest

from agent.marketplace_port import MarketplaceError
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter

CONTRACT = Path(__file__).resolve().parents[1] / "fixtures/marketplace_http_contract.json"


async def test_queries_auth_and_response_mapping():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"jobs": [{"job_id": "j1"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GigSimAdapter("http://fixture.test", CONTRACT, client, "fixture-token")
        assert await adapter.search_jobs("Python", 7) == [{"job_id": "j1"}]
    assert seen[0].url.path == "/fixture/jobs" and seen[0].url.params["q"] == "Python"
    assert seen[0].headers["Authorization"] == "Bearer fixture-token"


async def test_preview_and_namespaced_idempotency_are_forwarded():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"draft_id": "d1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GigSimAdapter("http://fixture.test", CONTRACT, client)
        await adapter.create_proposal_draft({"job_id": "j1"}, "same-key", True)
        await adapter.submit_proposal("d1", "same-key")
    assert json.loads(seen[0].content)["preview"] is True
    assert seen[0].headers["Idempotency-Key"] != seen[1].headers["Idempotency-Key"]


async def test_unverified_write_is_not_retried_or_provider_body_echoed():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(503, json={"message": "sensitive provider response"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GigSimAdapter("http://fixture.test", CONTRACT, client)
        with pytest.raises(MarketplaceError, match="HTTP 503") as error:
            await adapter.submit_proposal("d1", "key")
    assert len(seen) == 1 and "sensitive" not in str(error.value)


async def test_preview_without_mapping_sends_no_request(tmp_path):
    spec = json.loads(CONTRACT.read_text())
    del spec["operations"]["create_proposal_draft"]["json"]["preview"]
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps(spec))
    seen = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: seen.append(r))) as client:
        adapter = GigSimAdapter("http://fixture.test", contract, client)
        with pytest.raises(MarketplaceError, match="dry_run_unsupported"):
            await adapter.create_proposal_draft({}, "key", True)
    assert not seen


def test_no_silent_fake_instructor_endpoints(monkeypatch):
    monkeypatch.delenv("GIGSIM_API_URL", raising=False)
    monkeypatch.delenv("GIGSIM_CONTRACT", raising=False)
    with pytest.raises(ValueError, match="reviewed"):
        GigSimAdapter()
