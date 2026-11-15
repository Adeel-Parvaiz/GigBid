"""Actual LLM tool-granularity experiment: 40 tasks x 3 real MCP catalogs."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import tempfile
import time
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
import jsonschema
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session as connect

from evals.rd_a.run_experiment import DESCRIPTIONS, SERVER_FOR_TOOL, _decode_result, _matches, load_tasks
from mcp_servers.marketplace.adapters.sample import SampleAdapter
from mcp_servers.marketplace.server import build_server as market_server
from mcp_servers.marketplace.tools import MarketplaceService
from mcp_servers.portfolio.server import build_server as portfolio_server
from mcp_servers.portfolio.tools import PortfolioStore
from mcp_servers.workspace.server import build_server as workspace_server
from mcp_servers.workspace.tools import WorkspaceService

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'evals/results/rd_a_llm'
GROUPS = {s: [t for t, owner in SERVER_FOR_TOOL.items() if owner == s]
          for s in ('portfolio', 'marketplace', 'workspace')}


def task_request(task):
    """Make previously implicit fixture values explicit, without exposing the correct tool."""
    a = task['arguments']
    details = []
    labels = {'requirement': 'Exact search phrase', 'query': 'Exact search phrase', 'k': 'Maximum evidence items',
              'limit': 'Maximum results', 'days': 'Number of calendar days', 'duration_minutes': 'Meeting minutes',
              'title': 'Calendar title', 'body': 'Email body', 'subject': 'Email subject',
              'idempotency_key': 'Request key', 'start_date': 'Start date', 'start': 'Interview start'}
    for key, label in labels.items():
        if key in a:
            details.append(f'{label}: {json.dumps(a[key])}.')
    if 'proposal' in a:
        v = a['proposal']
        details += [f'Cover letter: {json.dumps(v["cover_letter"])}.', f'Bid: {v["bid_amount"]} USD.',
                    f'Request key: {v["idempotency_key"]}. No screening answers. Preview only.']
    return task['request'] + '\n' + ' '.join(details)


def canonical(arguments, schema, root=None):
    root = root or schema
    if '$ref' in schema:
        target = root
        for part in schema['$ref'].removeprefix('#/').split('/'):
            target = target[part]
        return canonical(arguments, target, root)
    if not isinstance(arguments, dict):
        return arguments
    value = dict(arguments)
    for key, prop in schema.get('properties', {}).items():
        if key not in value and 'default' in prop:
            value[key] = prop['default']
        if key in value:
            value[key] = canonical(value[key], prop, root)
    return value


def score_selection(tool, arguments, expected, coarse):
    if coarse:
        route = arguments.get('operation')
        selected = tool == SERVER_FOR_TOOL[expected] + '_operations' and route == expected
        return selected, route, arguments.get('arguments', {})
    return tool == expected, tool, arguments


async def trial(task, condition, base, rewritten, client, args):
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='gigbid-rda-') as temp:
        adapter = SampleAdapter(ROOT / 'data/sample')
        if task.get('setup') == 'seed_draft':
            await adapter.create_proposal_draft({'job_id': 'job-001', 'cover_letter': 'Prepared fixture draft.',
                                               'screening_answers': [], 'bid_amount': 300, 'currency': 'USD'}, 'rda-seed-key', False)
        servers = {'portfolio': portfolio_server(PortfolioStore(ROOT / 'data/sample', freelancer_id='sample-ai-engineer')),
                   'marketplace': market_server(MarketplaceService(adapter, Path(temp) / 'audit.jsonl', per_minute=1000)),
                   'workspace': workspace_server(WorkspaceService())}
        async with AsyncExitStack() as stack:
            sessions, schemas = {}, {}
            for owner, server in servers.items():
                sessions[owner] = await stack.enter_async_context(connect(server))
                for tool in (await sessions[owner].list_tools()).tools:
                    schemas[tool.name] = tool
            advertised, endpoints = [], {}
            if base == 'coarse':
                for owner, names in GROUPS.items():
                    combined = FastMCP(f'eval-{owner}-combined')

                    def handler_factory(server_owner, operations):
                        async def dispatch(operation: Literal[tuple(operations)], arguments: dict) -> dict:
                            result = await sessions[server_owner].call_tool(operation, arguments)
                            if result.isError:
                                raise ValueError(str(result.content))
                            return _decode_result(result)
                        # Resolve dynamic annotation before FastMCP/Pydantic evaluates it.
                        dispatch.__annotations__['operation'] = Literal[tuple(operations)]
                        return dispatch

                    contracts = {n: schemas[n].inputSchema for n in names}
                    description = ('Dispatch a portfolio, marketplace or workspace operation. '
                                   if not rewritten else
                                   'Select operation by intent, then pass only its arguments. Search discovers; get fetches a known ID. '
                                   'Draft/preview never submits. Submit and send require approval and a request key. ')
                    combined.tool(name=owner + '_operations', description=description + json.dumps(contracts))(
                        handler_factory(owner, names))
                    endpoint = await stack.enter_async_context(connect(combined))
                    for tool in (await endpoint.list_tools()).tools:
                        advertised.append({'name': tool.name, 'description': tool.description, 'inputSchema': tool.inputSchema})
                        endpoints[tool.name] = endpoint
            else:
                for name, tool in schemas.items():
                    description = DESCRIPTIONS['optimized'][name] if rewritten else tool.description
                    advertised.append({'name': name, 'description': description, 'inputSchema': tool.inputSchema})
                    endpoints[name] = sessions[SERVER_FOR_TOOL[name]]
            random.Random(args.seed + int(task['task_id'][1:])).shuffle(advertised)
            messages = [{'role': 'system', 'content': (ROOT / 'agent/prompts/rd_a_selector.md').read_text()
                         + '\nMCP catalog:\n' + json.dumps(advertised)},
                        {'role': 'user', 'content': task_request(task)}]
            response = await client.post(args.base_url.rstrip('/') + '/chat/completions', json={
                'model': args.model, 'messages': messages, 'temperature': 0, 'seed': args.seed,
                'max_tokens': 600, 'response_format': {'type': 'json_object'}})
            response.raise_for_status()
            body = response.json()
            usage = body.get('usage')
            if not usage or not all(k in usage for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')):
                raise RuntimeError('Provider did not return actual token counts')
            content = body['choices'][0]['message']['content']
            row = {'task_id': task['task_id'], 'condition': condition, 'base': base,
                   'request': task_request(task), 'expected_tool': task['expected_tool'], 'expected_arguments': task['arguments'],
                   'model': args.model, 'usage': usage, 'raw_response': content,
                   'catalog_sha256': hashlib.sha256(json.dumps(advertised, sort_keys=True).encode()).hexdigest(),
                   'tool_selection_correct': False, 'argument_accuracy': False, 'schema_valid': False,
                   'mcp_success': False, 'result_correct': False, 'error': None}
            try:
                call = json.loads(content)
                name, values = call['tool'], call['arguments']
                row['selected_tool'], row['selected_arguments'] = name, values
                correct, route, native = score_selection(name, values, task['expected_tool'], base == 'coarse')
                row['selected_operation'], row['tool_selection_correct'] = route, correct
                expected_schema = schemas[task['expected_tool']].inputSchema
                row['argument_accuracy'] = correct and canonical(native, expected_schema) == canonical(task['arguments'], expected_schema)
                spec = next(t for t in advertised if t['name'] == name)
                jsonschema.validate(values, spec['inputSchema'])
                # Combined arguments are validated by the underlying MCP server too.
                jsonschema.validate(native, schemas[route].inputSchema)
                row['schema_valid'] = True
                result = await endpoints[name].call_tool(name, values)
                row['mcp_success'] = not result.isError
                row['result_correct'] = correct and not result.isError and _matches(_decode_result(result), task['expect'])
            except (ValueError, KeyError, StopIteration, TypeError, jsonschema.ValidationError) as error:
                row['error'] = f'{type(error).__name__}: {str(error)[:400]}'
            row['argument_accuracy'] = row['argument_accuracy'] and row['schema_valid']
            row['seconds'] = round(time.perf_counter() - started, 3)
            return row


def aggregate(rows):
    return {condition: {
        'n': len(part), 'tool_selection_accuracy': sum(r['tool_selection_correct'] for r in part) / len(part),
        'argument_accuracy': sum(r['argument_accuracy'] for r in part) / len(part),
        'schema_validity': sum(r['schema_valid'] for r in part) / len(part),
        'completion_accuracy': sum(r['result_correct'] for r in part) / len(part),
        'mean_tokens_per_task': sum(r['usage']['total_tokens'] for r in part) / len(part),
        'mean_input_tokens': sum(r['usage']['prompt_tokens'] for r in part) / len(part),
        'mean_output_tokens': sum(r['usage']['completion_tokens'] for r in part) / len(part),
    } for condition in dict.fromkeys(r['condition'] for r in rows)
        if (part := [r for r in rows if r['condition'] == condition])}


async def run(args):
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()['tasks']
    (OUT / 'tasks.json').write_text(json.dumps([{**t, 'request': task_request(t)} for t in tasks], indent=2))
    rows = []
    if args.resume and (OUT / 'trials.jsonl').exists():
        rows = [json.loads(line) for line in (OUT / 'trials.jsonl').read_text().splitlines()]
        assert len({(r['condition'], r['task_id']) for r in rows}) == len(rows)
        assert all(r['model'] == args.model for r in rows)
        # Re-score saved responses with the same current default normalization.
        with tempfile.TemporaryDirectory() as temp:
            servers = [portfolio_server(PortfolioStore(ROOT / 'data/sample', freelancer_id='sample-ai-engineer')),
                       market_server(MarketplaceService(SampleAdapter(ROOT / 'data/sample'), Path(temp) / 'audit.jsonl')),
                       workspace_server(WorkspaceService())]
            schemas = {}
            for server in servers:
                async with connect(server) as session:
                    schemas.update({t.name: t.inputSchema for t in (await session.list_tools()).tools})
            for row in rows:
                if row['tool_selection_correct']:
                    native = row['selected_arguments']
                    if row['base'] == 'coarse':
                        native = native.get('arguments', {})
                    schema = schemas[row['expected_tool']]
                    row['argument_accuracy'] = row['schema_valid'] and canonical(native, schema) == canonical(row['expected_arguments'], schema)
        (OUT / 'trials.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    async with httpx.AsyncClient(timeout=150) as client:
        for condition, base in [('fine', 'fine'), ('coarse', 'coarse'), ('rewritten', None)]:
            if base is None:
                metrics = aggregate(rows)
                base = max(('fine', 'coarse'), key=lambda c: (metrics[c]['tool_selection_accuracy'], metrics[c]['argument_accuracy'], -metrics[c]['mean_tokens_per_task']))
            for task in tasks:
                if any(r['condition'] == condition and r['task_id'] == task['task_id'] for r in rows):
                    continue
                row = await trial(task, condition, base, condition == 'rewritten', client, args)
                rows.append(row)
                with (OUT / 'trials.jsonl').open('a' if len(rows) > 1 else 'w') as output:
                    output.write(json.dumps(row) + '\n')
                print(condition, task['task_id'], row['tool_selection_correct'], row['argument_accuracy'], row['usage']['total_tokens'], flush=True)
    report = {'created_at': datetime.now(UTC).isoformat(), 'model': args.model, 'base_url': args.base_url,
              'seed': args.seed, 'temperature': 0, 'trials': len(rows), 'rewritten_base': rows[-1]['base'],
              'metrics': aggregate(rows), 'tasks_sha256': hashlib.sha256((OUT / 'tasks.json').read_bytes()).hexdigest(),
              'scope': 'Real open-weight LLM selects tool AND generates arguments, executed through official SDK in-memory MCP. Disposable synthetic fixtures only.'}
    (OUT / 'aggregate.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:11435/v1')
    parser.add_argument('--model', default='qwen25-15b')
    parser.add_argument('--seed', type=int, default=4016)
    parser.add_argument('--resume', action='store_true', help='Keep completed model responses and run only missing trials')
    asyncio.run(run(parser.parse_args()))
