"""Isolated viva/test stack with real, killable marketplace processes. Never imported by production."""
import argparse
import asyncio
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def create_app():
    import uvicorn  # noqa: F401
    from fastapi import Depends

    root = Path(__file__).resolve().parents[2]
    temporary = tempfile.TemporaryDirectory(prefix='gigbid-a6-')
    state = Path(temporary.name)
    rest_port, mcp_port = free_port(), free_port()
    os.environ.update({'GIGBID_DATA_DIR': str(root / 'data/sample'), 'PORTFOLIO_DIR': str(root / 'data/sample'),
                       'LLM_BACKEND': 'heuristic', 'USERS_DB': str(state / 'users.sqlite'),
                       'RUNS_DB': str(state / 'runs.sqlite'), 'DATABASE_URL': f'sqlite:///{state / "checkpoints.sqlite"}',
                       'OAUTH_DB': str(state / 'oauth.sqlite'), 'WORKSPACE_DB': str(state / 'workspace.sqlite'),
                       'APP_SECRET_KEY': 'isolated-a6-fixture-secret', 'REVIEWER_PERSONA': 'sample-ai-engineer',
                       'REVIEWER_EMAIL': 'reviewer@gigbid.test', 'REVIEWER_PASSWORD': 'reviewer-pass-1',
                       'MARKETPLACE_MCP_TOKEN': 'a6-mcp-token', 'DEGRADED_RECOVERY_INTERVAL': '.5'})
    env = {**os.environ, 'GIGSIM_DB': str(state / 'market.sqlite'),
           'GIGSIM_TOKENS_JSON': json.dumps({'a6-upstream-token': 'a6-reviewer'}), 'GIGSIM_API_TOKEN': 'a6-upstream-token',
           'GIGSIM_API_URL': f'http://127.0.0.1:{rest_port}', 'GIGSIM_CONTRACT': str(root / 'config/gigsim_contract.json'),
           'MARKETPLACE_MODE': 'gigsim', 'MARKETPLACE_MCP_TOKENS': 'a6-mcp-token:a6-reviewer',
           'MARKETPLACE_AUDIT': str(state / 'audit.jsonl'), 'MARKETPLACE_RPM': '1000', 'PORT': str(mcp_port)}
    rest = None
    marketplace = None

    def spawn(command, label):
        with (state / f'{label}.log').open('a') as log:
            return subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=log)

    async def ready(process, port):
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('Isolated marketplace process failed to start')
            try:
                socket.create_connection(('127.0.0.1', port), timeout=.1).close()
                return
            except OSError:
                await asyncio.sleep(.1)
        raise TimeoutError('Isolated service startup')

    async def start_market():
        nonlocal marketplace
        if marketplace is None or marketplace.poll() is not None:
            marketplace = spawn([sys.executable, '-m', 'mcp_servers.marketplace.server'], 'marketplace')
            await ready(marketplace, mcp_port)

    from agent.config import load_config
    from agent.marketplace_mcp import build_mcp_port
    from agent.runtime import build_deps
    from apps.api.deps import get_user
    from apps.api.main import create_app as api_app

    cfg = load_config(overrides={'marketplace': {'mode': 'mcp', 'url': f'http://127.0.0.1:{mcp_port}/mcp'},
                                 'portfolio': {'source': 'mcp', 'transport': 'stdio'},
                                 'workspace': {'source': 'mcp', 'transport': 'stdio'}})
    deps = build_deps(cfg, port=build_mcp_port(cfg, timeout=.6, retries=1))
    app = api_app(deps=deps)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        nonlocal rest
        rest = spawn([sys.executable, '-m', 'uvicorn', 'apps.gigsim.main:create_app', '--factory', '--port', str(rest_port)], 'gigsim')
        try:
            await ready(rest, rest_port)
            await start_market()
            async with original(application):
                yield
        finally:
            for process in [marketplace, rest]:
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(10)
            temporary.cleanup()

    app.router.lifespan_context = lifespan

    def admin(user: dict = Depends(get_user)):
        if user['email'] != 'reviewer@gigbid.test':
            from fastapi import HTTPException
            raise HTTPException(403, 'Fixture controls require the isolated reviewer')

    @app.post('/_testing/marketplace/kill', dependencies=[Depends(admin)])
    async def kill():
        if marketplace and marketplace.poll() is None:
            marketplace.kill()
            marketplace.wait(5)
        return {'stopped': True}

    @app.post('/_testing/marketplace/start', dependencies=[Depends(admin)])
    async def start():
        await start_market()
        return {'started': True, 'pid': marketplace.pid}

    @app.get('/_testing/state', dependencies=[Depends(admin)])
    async def inspect():
        with sqlite3.connect(state / 'market.sqlite') as database:
            row = database.execute('SELECT state FROM accounts WHERE id=?', ('a6-reviewer',)).fetchone()
        stored = json.loads(row[0]) if row else {}
        return {'balance': stored.get('balance', 100), 'drafts': len(stored.get('drafts', {})),
                'submissions': len(stored.get('submissions', {})), 'sent': len(stored.get('sent', {})),
                'marketplace_pid': marketplace.pid, 'marketplace_running': marketplace.poll() is None}

    return app


if __name__ == '__main__':
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18040)
    args = parser.parse_args()
    uvicorn.run(create_app(), host='127.0.0.1', port=args.port)
