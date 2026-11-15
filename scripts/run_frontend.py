"""Start the existing GigBid frontend using system Node or the project-local WSL runtime."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    cached = sorted((ROOT / ".local-models/node-runtime").glob("node-*/bin/node"))
    executable = str(cached[-1]) if cached else shutil.which("node")
    if not executable:
        raise SystemExit("Node.js is not installed in this environment. Use the configured WSL project or install Node.js.")
    node = Path(executable)
    env = {**os.environ, "PATH": str(node.parent) + os.pathsep + os.environ.get("PATH", "")}
    web = ROOT / "apps/web"
    vite = web / "node_modules/vite/bin/vite.js"
    if not vite.exists():
        npm = shutil.which("npm", path=env["PATH"])
        if not npm:
            raise SystemExit("npm is missing from the selected Node installation.")
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=web, env=env, check=True)
    print("GigBid frontend: http://localhost:3000 (API proxy: localhost:8000)", flush=True)
    raise SystemExit(subprocess.call([str(node), str(vite), "--host", "127.0.0.1", "--port", "3000", "--strictPort"], cwd=web, env=env))


if __name__ == "__main__":
    main()
