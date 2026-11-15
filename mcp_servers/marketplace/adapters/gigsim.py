"""REST marketplace adapter requiring a reviewed contract; instructor endpoints are not guessed."""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import httpx

from agent.marketplace_port import MarketplaceError

OPERATIONS = {"search_jobs", "get_job", "get_client_history", "get_connects_balance", "create_proposal_draft",
              "submit_proposal", "list_threads", "list_messages", "send_message"}
WRITES = {"create_proposal_draft", "submit_proposal", "send_message"}


def render(template, arguments):
    if isinstance(template, dict):
        return {k: render(v, arguments) for k, v in template.items()}
    if isinstance(template, list):
        return [render(v, arguments) for v in template]
    if isinstance(template, str) and template.startswith("$"):
        value = arguments
        for key in template[1:].split("."):
            value = value[key]
        return value
    return template


def select(document, pointer):
    if not pointer:
        return document
    if not pointer.startswith("/"):
        raise ValueError("Expected an RFC 6901 JSON pointer")
    for key in pointer[1:].split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        document = document[int(key)] if isinstance(document, list) else document[key]
    return document


class GigSimAdapter:
    def __init__(self, base_url=None, contract_path=None, client=None, token=None):
        base_url = base_url or os.environ.get("GIGSIM_API_URL")
        contract_path = contract_path or os.environ.get("GIGSIM_CONTRACT")
        if not base_url or not contract_path:
            raise ValueError("GigSim needs GIGSIM_API_URL and a reviewed GIGSIM_CONTRACT; instructor documentation is not bundled")
        self.contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
        self.operations = self.contract["operations"]
        if OPERATIONS - self.operations.keys():
            raise ValueError(f"Missing operations: {sorted(OPERATIONS - self.operations.keys())}")
        for name, op in self.operations.items():
            if not op["path"].startswith("/") or op["path"].startswith("//") or "://" in op["path"]:
                raise ValueError(f"{name}: paths must stay on the configured API origin")
            if op["method"] not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                raise ValueError(f"{name}: invalid HTTP method")
        self.base_url = base_url.rstrip("/")
        self.client, self.owns_client = client, client is None
        self.headers = {}
        token = token if token is not None else os.environ.get("GIGSIM_API_TOKEN", "")
        if token:
            self.headers[self.contract.get("auth_header", "Authorization")] = f"{self.contract.get('auth_scheme', 'Bearer')} {token}".strip()

    async def aclose(self):
        if self.client and self.owns_client:
            await self.client.aclose()

    async def _call(self, name, **arguments):
        op, headers = self.operations[name], dict(self.headers)
        if name in WRITES:
            if not arguments.get("idempotency_key"):
                raise MarketplaceError("idempotency_key_required")
            arguments["idempotency_key"] = f"{name}:{arguments['idempotency_key']}"
            header = self.contract.get("idempotency_header")
            if not header:
                raise MarketplaceError("contract_error", "write idempotency header must be explicitly mapped")
            headers[header] = arguments["idempotency_key"]
        if name == "create_proposal_draft" and arguments.get("dry_run") and '"$dry_run"' not in json.dumps(op):
            raise MarketplaceError("dry_run_unsupported", "preview flag is not mapped; no request sent")

        def path_value(match):
            value = str(arguments[match.group(1)])
            if value in {".", ".."}:
                raise MarketplaceError("invalid_id")
            return quote(value, safe="")

        try:
            path = re.sub(r"\{([a-z_]+)\}", path_value, op["path"])
            params = {k: v for k, v in render(op.get("params", {}), arguments).items() if v is not None}
            body = render(op.get("json"), arguments)
        except (KeyError, TypeError) as error:
            raise MarketplaceError("contract_error", "request template references an unavailable argument") from error
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=8, follow_redirects=False)
        attempts = 3 if name not in WRITES or self.contract.get("idempotent_writes_verified") is True else 1
        for attempt in range(attempts):
            try:
                response = await self.client.request(op["method"], self.base_url + path, params=params, json=body, headers=headers)
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt + 1 < attempts:
                    await asyncio.sleep(.1 * 2**attempt)
                    continue
                raise MarketplaceError("marketplace_unavailable", type(error).__name__) from error
            if response.status_code in {429, 502, 503, 504} and attempt + 1 < attempts:
                try:
                    delay = float(response.headers.get("Retry-After", .1 * 2**attempt))
                except ValueError:
                    delay = .1 * 2**attempt
                await asyncio.sleep(min(2, max(0, delay)))
                continue
            if not response.is_success:
                codes = {401: "unauthorized", 403: "forbidden", 429: "rate_limited"}
                missing = "thread_not_found" if name == "list_messages" else "draft_not_found" if name == "submit_proposal" else "job_not_found"
                code = missing if response.status_code == 404 else codes.get(response.status_code, "marketplace_unavailable" if response.status_code >= 500 else "marketplace_error")
                raise MarketplaceError(code, f"HTTP {response.status_code}")
            try:
                return select(response.json(), op.get("response_pointer", ""))
            except (ValueError, KeyError, TypeError, IndexError) as error:
                raise MarketplaceError("contract_error", "response does not match configured JSON mapping") from error
        raise AssertionError("unreachable")

    async def search_jobs(self, query=None, limit=20):
        return await self._call("search_jobs", query=query, limit=limit)

    async def get_job(self, job_id):
        return await self._call("get_job", job_id=job_id)

    async def get_client_history(self, client_id):
        return await self._call("get_client_history", client_id=client_id)

    async def get_connects_balance(self):
        return await self._call("get_connects_balance")

    async def create_proposal_draft(self, payload, idempotency_key, dry_run=False):
        return await self._call("create_proposal_draft", payload=payload, idempotency_key=idempotency_key, dry_run=dry_run)

    async def submit_proposal(self, draft_id, idempotency_key):
        return await self._call("submit_proposal", draft_id=draft_id, idempotency_key=idempotency_key)

    async def list_threads(self):
        return await self._call("list_threads")

    async def list_messages(self, thread_id):
        return await self._call("list_messages", thread_id=thread_id)

    async def send_message(self, thread_id, text, idempotency_key):
        return await self._call("send_message", thread_id=thread_id, text=text, idempotency_key=idempotency_key)
