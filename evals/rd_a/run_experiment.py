"""Run the R&D A description experiment with the deterministic lexical selector.

Usage: python -m evals.rd_a.run_experiment
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import time
from contextlib import AsyncExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import jsonschema
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_servers.marketplace.adapters.sample import DATA, SampleAdapter
from mcp_servers.marketplace.server import build_server as build_marketplace_server
from mcp_servers.marketplace.tools import MarketplaceService
from mcp_servers.portfolio.server import build_server as build_portfolio_server
from mcp_servers.portfolio.tools import PortfolioStore
from mcp_servers.workspace.server import build_server as build_workspace_server
from mcp_servers.workspace.tools import WorkspaceService
from rag.index.bm25 import BM25Index

ROOT = Path(__file__).resolve().parents[2]
TASKS_PATH = Path(__file__).with_name("tasks.json")
RESULTS_PATH = Path(__file__).with_name("results") / "task_results.jsonl"

DESCRIPTIONS: dict[str, dict[str, str]] = {
    "fine_grained": {
        "search_evidence": "Search portfolio evidence for one requirement, skill, tool, or deliverable. Use for finding matching proof; returns evidence items. Query one requirement at a time.",
        "get_case_study": "Fetch one already-known portfolio item by its exact evidence ID. Use after an item ID is available; does not search for items.",
        "list_skills": "List the freelancer's portfolio skills and the number of items mentioning each skill. Use for a complete skill inventory.",
        "search_jobs": "Search open marketplace job posts using a keyword query and result limit. Returns matching listings; does not retrieve a specified job by ID.",
        "get_job": "Retrieve the complete marketplace posting for one known job ID, including untrusted description text and requirements.",
        "get_client_history": "Retrieve one client's marketplace history by client ID: completed projects, rating, and payment verification.",
        "get_connects_balance": "Read the current remaining Connects balance. This is a read-only balance check and does not spend Connects.",
        "list_threads": "List conversation threads and their associated job, client, and last-message summary. Does not return full message history.",
        "list_messages": "Retrieve the full message history for one known conversation thread ID. Does not send a message.",
        "create_proposal_draft": "Create or preview a proposal draft for a job. Set proposal.dry_run=true to preview without creating it or spending Connects; this tool never submits.",
        "submit_proposal": "Submit an existing proposal draft by draft ID after human approval. This spends Connects; requires an idempotency key.",
        "send_message": "Send an approved text message to an existing client conversation thread. This sends externally; requires an idempotency key.",
        "get_free_slots": "List available working-day interview times from a start date for a requested duration and result limit.",
        "create_tentative_hold": "Create a tentative, not confirmed, calendar hold for a specific interview time. Requires title and idempotency key.",
        "create_email_draft": "Save a recipient, subject, and body as an unsent email draft for a human to send. Requires an idempotency key.",
    },
    "coarse_grained": {
        "search_evidence": "Portfolio service: access freelancer work information, proof, and skills.",
        "get_case_study": "Portfolio service: access freelancer work information, proof, and skills.",
        "list_skills": "Portfolio service: access freelancer work information, proof, and skills.",
        "search_jobs": "Marketplace service: access jobs, clients, proposals, Connects, and conversations.",
        "get_job": "Marketplace service: access jobs, clients, proposals, Connects, and conversations.",
        "get_client_history": "Marketplace service: access jobs, clients, proposals, Connects, and conversations.",
        "get_connects_balance": "Marketplace service: access jobs, clients, proposals, Connects, and conversations.",
        "list_threads": "Marketplace service: access jobs, clients, proposals, Connects, and conversations.",
        "list_messages": "Marketplace service: access jobs, clients, proposals, Connects, and conversations.",
        "create_proposal_draft": "Marketplace service: access jobs, clients, proposals, Connects, and conversations.",
        "submit_proposal": "Marketplace service: access jobs, clients, proposals, Connects, and conversations.",
        "send_message": "Marketplace service: access jobs, clients, proposals, Connects, and conversations.",
        "get_free_slots": "Workspace service: access calendar and email, including availability and meeting follow-up.",
        "create_tentative_hold": "Workspace service: access calendar and email, including availability and meeting follow-up.",
        "create_email_draft": "Workspace service: access calendar and email, including availability and meeting follow-up.",
    },
    "optimized": {
        "search_evidence": "Find portfolio proof matching a skill, tool, or deliverable. Use a requirement phrase; returns evidence items. For a known evidence ID use get_case_study; for all portfolio skills use list_skills.",
        "get_case_study": "Fetch one portfolio item when you already know its evidence_id. For semantic matching use search_evidence; for the full skill inventory use list_skills.",
        "list_skills": "Return every skill in the portfolio with item counts. Use for inventory, not evidence search (search_evidence) or fetching a known item (get_case_study).",
        "search_jobs": "Find open marketplace listings by keyword (query, limit). Use to discover matching jobs; use get_job only when you already have a job_id.",
        "get_job": "Fetch one marketplace job post by its known job_id. For keyword discovery across open listings use search_jobs.",
        "get_client_history": "Look up a client's past projects, rating, and payment verification using client_id. This is not a job-post lookup.",
        "get_connects_balance": "Read the freelancer's remaining Connects. No Connects are spent by this balance check; submission uses submit_proposal.",
        "list_threads": "List conversation thread summaries (thread_id, job, client, latest message). To read a thread's full messages use list_messages.",
        "list_messages": "Read all messages for one known thread_id. This does not send anything; to send an approved reply use send_message.",
        "create_proposal_draft": "Create a proposal draft or safe preview for a job. Set proposal.dry_run=true for a preview that creates nothing and spends no Connects. Never submits; submit_proposal is the separate post-approval action.",
        "submit_proposal": "Submit a previously created proposal draft only after human approval; spends Connects and requires draft_id plus idempotency_key. Draft creation/preview is create_proposal_draft.",
        "send_message": "Send text to a known client thread only after human approval; this is an external write and requires thread_id and idempotency_key. Reading uses list_messages.",
        "get_free_slots": "Find open calendar interview times from start_date, with days, duration_minutes, and limit. Read-only; creating a tentative hold is create_tentative_hold.",
        "create_tentative_hold": "Place a tentative (not confirmed) calendar hold for a specified start time and title. Requires idempotency_key; finding free times is get_free_slots.",
        "create_email_draft": "Save an email as a draft (never sends it) using to, subject, body, and idempotency_key. Calendar holds use create_tentative_hold.",
    },
}

SERVER_FOR_TOOL = {
    "search_evidence": "portfolio", "get_case_study": "portfolio", "list_skills": "portfolio",
    "search_jobs": "marketplace", "get_job": "marketplace", "get_client_history": "marketplace",
    "get_connects_balance": "marketplace", "list_threads": "marketplace", "list_messages": "marketplace",
    "create_proposal_draft": "marketplace", "submit_proposal": "marketplace", "send_message": "marketplace",
    "get_free_slots": "workspace", "create_tentative_hold": "workspace", "create_email_draft": "workspace",
}


def load_tasks(path: Path = TASKS_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    ids = [task.get("task_id") for task in tasks]
    if len(tasks) != 40 or len(set(ids)) != 40:
        raise ValueError(f"R&D A requires exactly 40 tasks with unique IDs; found {len(tasks)}")
    if set(DESCRIPTIONS) != {"fine_grained", "coarse_grained", "optimized"}:
        raise ValueError("The experiment must define all three description conditions")
    if any(set(descriptions) != set(SERVER_FOR_TOOL) for descriptions in DESCRIPTIONS.values()):
        raise ValueError("Description conditions must cover the unchanged MCP tool set")
    if any(task["expected_tool"] not in SERVER_FOR_TOOL for task in tasks):
        raise ValueError("A task references a tool outside the existing MCP tool set")
    return data


def _tool_document(tool: Any) -> dict[str, Any]:
    schema = tool.inputSchema
    fields = schema.get("properties", {})
    field_text = " ".join(
        f"{name} {definition.get('description', '')}"
        for name, definition in sorted(fields.items())
    )
    return {"title": tool.name, "summary": f"{tool.description or ''} {field_text}",
            "skills": list(fields)}


def _schema_fingerprint(tools: dict[str, Any]) -> str:
    data = {
        name: {
            "inputSchema": tool.inputSchema,
            "outputSchema": tool.outputSchema,
            "annotations": tool.annotations.model_dump(exclude_none=True) if tool.annotations else None,
        }
        for name, tool in sorted(tools.items())
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _decode_result(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    texts = [item.text for item in getattr(result, "content", []) if getattr(item, "text", None)]
    if not texts:
        return None
    text = "\n".join(texts)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _get_path(value: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _matches(result: Any, expect: dict[str, Any]) -> bool:
    actual = _get_path(result, expect["path"])
    op, expected = expect["operator"], expect.get("value")
    if op == "nonempty":
        return isinstance(actual, (str, list, dict)) and len(actual) > 0
    if op == "equals":
        return actual == expected
    if op == "greater_than":
        return isinstance(actual, (int, float)) and actual > expected
    raise ValueError(f"Unsupported task expectation operator: {op}")


async def _run_trial(task: dict[str, Any], config_name: str, seed: int) -> tuple[dict[str, Any], str]:
    descriptions = DESCRIPTIONS[config_name]
    start_total = time.perf_counter()
    schemas: dict[str, Any] = {}
    clients: dict[str, Any] = {}

    with TemporaryDirectory(prefix="gigbid-rd-a-") as temp_dir:
        adapter = SampleAdapter(DATA)
        if task.get("setup") == "seed_draft":
            payload = {"job_id": "job-001", "cover_letter": "A prepared local evaluation draft.",
                       "screening_answers": [], "bid_amount": 300, "currency": "USD"}
            await adapter.create_proposal_draft(payload, "rdA-setup-key", dry_run=False)
        market_service = MarketplaceService(adapter, Path(temp_dir) / "market-audit.jsonl", per_minute=1000)
        servers = {
            "portfolio": build_portfolio_server(PortfolioStore(DATA), descriptions),
            "marketplace": build_marketplace_server(market_service, descriptions),
            "workspace": build_workspace_server(WorkspaceService(), descriptions),
        }
        async with AsyncExitStack() as stack:
            for server_name, server in servers.items():
                client = await stack.enter_async_context(create_connected_server_and_client_session(server))
                clients[server_name] = client
                for tool in (await client.list_tools()).tools:
                    if tool.name in schemas:
                        raise ValueError(f"Duplicate MCP tool name: {tool.name}")
                    schemas[tool.name] = tool

            if len(schemas) != 15:
                raise ValueError(f"Expected 15 live MCP tools, found {len(schemas)}")

            selection_docs = [_tool_document(tool) for tool in schemas.values()]
            selection_start = time.perf_counter()
            matches = BM25Index(selection_docs).search(task["request"], k=1)
            selected = matches[0]["title"] if matches else sorted(schemas)[0]
            selection_latency_ms = (time.perf_counter() - selection_start) * 1000

            args = task["arguments"]
            schema_valid = True
            schema_error = None
            try:
                jsonschema.validate(args, schemas[selected].inputSchema)
            except jsonschema.ValidationError as exc:
                schema_valid = False
                schema_error = exc.message

            call_start = time.perf_counter()
            is_error, error_text, parsed = False, None, None
            calls = 0
            try:
                calls = 1
                result = await clients[SERVER_FOR_TOOL[selected]].call_tool(selected, args)
                is_error = bool(getattr(result, "isError", False))
                parsed = _decode_result(result)
                if is_error:
                    error_text = str(parsed)
            except Exception as exc:  # benchmark row records actual tool-call failure
                is_error, error_text = True, f"{type(exc).__name__}: {exc}"
            tool_latency_ms = (time.perf_counter() - call_start) * 1000
            tool_completed = not is_error and _matches(parsed, task["expect"])
            selection_correct = selected == task["expected_tool"]
            completed = selection_correct and schema_valid and tool_completed
            schema_fingerprint = _schema_fingerprint(schemas)
            description_fingerprint = hashlib.sha256(
                json.dumps(descriptions, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            row = {
                "task_id": task["task_id"],
                "configuration": config_name,
                "configuration_sha256": description_fingerprint,
                "schema_sha256": schema_fingerprint,
                "expected_tool": task["expected_tool"],
                "selected_tool": selected,
                "correct_tool_selection": selection_correct,
                "task_completed": completed,
                "tool_result_satisfied_expectation": tool_completed,
                "argument_schema_valid": schema_valid,
                "schema_error": schema_error,
                "tool_calls": calls,
                "failed_tool_calls": int(is_error),
                "selection_latency_ms": round(selection_latency_ms, 3),
                "tool_latency_ms": round(tool_latency_ms, 3),
                "latency_ms": round((time.perf_counter() - start_total) * 1000, 3),
                "token_usage": None,
                "cost_usd": None,
                "error": error_text,
                "seed": seed,
            }
            return row, schema_fingerprint


async def run(tasks_data: dict[str, Any], seed: int = 4016) -> list[dict[str, Any]]:
    random.seed(seed)
    rows = []
    fingerprints: set[str] = set()
    task_ids = [task["task_id"] for task in tasks_data["tasks"]]
    for config_name in ("fine_grained", "coarse_grained", "optimized"):
        config_rows = []
        for task in tasks_data["tasks"]:
            row, fingerprint = await _run_trial(task, config_name, seed)
            rows.append(row)
            config_rows.append(row["task_id"])
            fingerprints.add(fingerprint)
        if config_rows != task_ids:
            raise AssertionError(f"{config_name} did not run the exact same task sequence")
    if len(rows) != 120:
        raise AssertionError(f"Expected 120 trials (40 tasks x 3 conditions), got {len(rows)}")
    if len(fingerprints) != 1:
        raise AssertionError("MCP schemas or annotations changed between description conditions")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, default=TASKS_PATH)
    parser.add_argument("--output", type=Path, default=RESULTS_PATH)
    parser.add_argument("--seed", type=int, default=4016)
    args = parser.parse_args()
    tasks_data = load_tasks(args.tasks)
    rows = asyncio.run(run(tasks_data, args.seed))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"trials": len(rows), "tasks_per_condition": 40, "seed": args.seed,
                      "results": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
