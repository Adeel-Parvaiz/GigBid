"""Launch disposable sample servers and the official Inspector for A7 screenshots."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wait_port(port: int, process: subprocess.Popen) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError('Fixture process exited; inspect the temporary logs')
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2):
                return
        except OSError:
            time.sleep(.1)
    raise TimeoutError(f'Local fixture port {port} did not start')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', default=shutil.which('node'))
    parser.add_argument('--inspector-root', type=Path, default=ROOT / '.local-models/mcp-inspector')
    args = parser.parse_args()
    launcher = args.inspector_root / 'node_modules/@modelcontextprotocol/inspector/clients/launcher/build/index.js'
    if not args.node or not launcher.is_file():
        parser.error('Install Node and @modelcontextprotocol/inspector@2.15.0 first; see docs/MCP_TESTING.md')
    ports = (16274, 16275, 16278, 16281)
    for port in ports:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    children = []
    with tempfile.TemporaryDirectory(prefix='gigbid-inspector-') as directory:
        state = Path(directory)
        token = secrets.token_urlsafe(24)
        sample = str(ROOT / 'data/sample')
        config = {'mcpServers': {
            'GigBid Portfolio': {'type': 'stdio', 'command': sys.executable,
                'args': ['-m', 'mcp_servers.portfolio.server'], 'cwd': str(ROOT),
                'env': {'GIGBID_DATA_DIR': sample, 'PORTFOLIO_DIR': sample,
                        'PORTFOLIO_FREELANCER_ID': 'sample-ai-engineer'}},
            'GigBid Marketplace': {'type': 'streamable-http', 'url': 'http://127.0.0.1:16281/mcp',
                'headers': {'Authorization': f'Bearer {token}'}},
            'GigBid Workspace': {'type': 'stdio', 'command': sys.executable,
                'args': ['-m', 'mcp_servers.workspace.server'], 'cwd': str(ROOT),
                'env': {'WORKSPACE_DB': str(state / 'workspace.sqlite')}},
        }}
        catalog = state / 'servers.json'
        catalog.write_text(json.dumps(config))
        env = {**os.environ, 'HOST': '127.0.0.1', 'PORT': '16281', 'MARKETPLACE_MODE': 'sample',
               'GIGBID_DATA_DIR': sample, 'MARKETPLACE_MCP_TOKENS': f'{token}:inspector-reviewer',
               'MARKETPLACE_AUDIT': str(state / 'audit.jsonl'), 'MARKETPLACE_RPM': '1000',
               'CLIENT_PORT': '16274', 'MCP_SANDBOX_PORT': '16275', 'MCP_APP_ORIGIN_PORT': '16278',
               'MCP_INSPECTOR_API_TOKEN': secrets.token_hex(32), 'MCP_AUTO_OPEN_ENABLED': 'false',
               'BROWSER': 'none', 'MCP_STORAGE_DIR': str(state / 'storage'),
               'MCP_INSPECTOR_OAUTH_STATE_PATH': str(state / 'oauth.json'),
               'MCP_CLIENT_CONFIG_PATH': str(state / 'client.json')}
        try:
            with (state / 'services.log').open('w') as log:
                for command, port in [
                    ([sys.executable, '-m', 'mcp_servers.marketplace.server'], 16281),
                    ([args.node, str(launcher), '--web', '--config', str(catalog), '--server', 'GigBid Portfolio'], 16274),
                ]:
                    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                                               stderr=log, start_new_session=os.name != 'nt')
                    children.append(process)
                    wait_port(port, process)
                subprocess.run([args.node, 'evals/inspectors/capture.cjs'], cwd=ROOT, env=env, check=True)
        finally:
            for process in reversed(children):
                if process.poll() is None:
                    if os.name != 'nt':
                        os.killpg(process.pid, signal.SIGTERM)
                    else:
                        process.terminate()
                    process.wait(timeout=15)


if __name__ == '__main__':
    main()
