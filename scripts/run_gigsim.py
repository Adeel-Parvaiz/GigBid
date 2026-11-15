"""Run the project-owned GigSim REST service, marketplace MCP, and optionally GigBid API."""
import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-api', action='store_true')
    parser.add_argument('--port', type=int, default=8003)
    parser.add_argument('--mcp-port', type=int, default=8001)
    parser.add_argument('--data-dir', type=Path, default=root / 'data/processed/kaggle_2024_v1')
    args = parser.parse_args()
    load_dotenv(root / '.env', override=False)
    if not (args.data_dir / 'jobs.json').exists():
        raise SystemExit('Dataset missing; run python -m scripts.prepare_dataset first.')
    state = root / '.local-models/gigsim'
    state.mkdir(parents=True, exist_ok=True)
    credential_file = state / 'local-tokens.json'
    if not credential_file.exists():
        # Separate upstream and MCP credentials, persistent across local restarts.
        with credential_file.open('x') as f:
            credential_file.chmod(0o600)
            json.dump({'upstream': secrets.token_hex(32), 'mcp': secrets.token_hex(32)}, f)
    credentials = json.loads(credential_file.read_text())
    env = {**os.environ, 'GIGBID_DATA_DIR': str(args.data_dir.resolve()),
           'GIGSIM_TOKENS_JSON': json.dumps({credentials['upstream']: 'local-reviewer'}),
           'GIGSIM_DB': str(state / 'state.sqlite'), 'GIGSIM_API_URL': f'http://127.0.0.1:{args.port}',
           'GIGSIM_CONTRACT': str(root / 'config/gigsim_contract.json'),
           'GIGSIM_API_TOKEN': credentials['upstream'], 'MARKETPLACE_MODE': 'gigsim',
           'MARKETPLACE_MCP_TOKENS': f"{credentials['mcp']}:local-reviewer", 'MARKETPLACE_MCP_TOKEN': credentials['mcp'],
           'MARKETPLACE_AUDIT': str(state / 'mcp-audit.jsonl'), 'PORT': str(args.mcp_port),
           'GIGBID__marketplace__mode': 'mcp', 'GIGBID__marketplace__url': f'http://127.0.0.1:{args.mcp_port}/mcp',
           'GIGBID__workspace__source': 'mcp', 'GIGBID__workspace__transport': 'stdio',
           'GIGBID__portfolio__source': 'mcp', 'GIGBID__portfolio__transport': 'stdio',
           'PORTFOLIO_DIR': str(args.data_dir.resolve()),
           'WORKSPACE_DB': str(state / 'workspace.sqlite')}
    processes = []
    try:
        commands = [([sys.executable, '-m', 'uvicorn', 'apps.gigsim.main:create_app', '--factory', '--host', '127.0.0.1', '--port', str(args.port)],
                     f'http://127.0.0.1:{args.port}/health'),
                    ([sys.executable, '-m', 'mcp_servers.marketplace.server'], f'http://127.0.0.1:{args.mcp_port}/mcp')]
        if args.with_api:
            from scripts.run_dataset import configure_local_state
            configure_local_state(root / '.local-models/api-state')
            env.update({k: os.environ[k] for k in ['DATABASE_URL', 'RUNS_DB', 'USERS_DB', 'APP_SECRET_KEY']})
            commands.append(([sys.executable, '-m', 'uvicorn', 'apps.api.main:create_app', '--factory', '--host', '127.0.0.1', '--port', '8000'], 'http://127.0.0.1:8000/docs'))
        for command, url in commands:
            process = subprocess.Popen(command, cwd=root, env=env)
            processes.append(process)
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError('Service exited during startup; inspect its log above.')
                try:
                    response = httpx.get(url, timeout=.3)
                    if response.status_code < 500:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.1)
            else:
                raise RuntimeError(f'Service startup timed out: {url}')
        print(f'GigSim: http://127.0.0.1:{args.port}; MCP: http://127.0.0.1:{args.mcp_port}/mcp', flush=True)
        print('Synthetic marketplace running. Ctrl+C stops launched services. Credentials are stored locally, not printed.', flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
