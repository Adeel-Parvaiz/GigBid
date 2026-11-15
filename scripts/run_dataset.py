"""Start the API with the versioned corpus and the offline development backend."""
from __future__ import annotations

import argparse
import asyncio
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

from scripts.prepare_dataset import CORPUS


def configure_local_state(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{directory / 'checkpoints.sqlite'}")
    os.environ.setdefault("RUNS_DB", str(directory / "runs.sqlite"))
    os.environ.setdefault("USERS_DB", str(directory / "users.sqlite"))
    if not os.environ.get("APP_SECRET_KEY"):
        secret_file = directory / "session-secret"
        if not secret_file.exists():
            secret_file.write_text(secrets.token_hex(32))
            secret_file.chmod(0o600)
        os.environ["APP_SECRET_KEY"] = secret_file.read_text().strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check marketplace and portfolio loading without starting the API")
    args = parser.parse_args()
    load_dotenv(CORPUS.parents[2] / ".env", override=False)
    if not (CORPUS / "DATA_MANIFEST.json").exists():
        raise SystemExit("Corpus missing. Run python -m scripts.prepare_dataset first.")
    os.environ["GIGBID_DATA_DIR"] = str(CORPUS)
    os.environ["PORTFOLIO_DIR"] = str(CORPUS)
    os.environ.setdefault('GIGBID__portfolio__source', 'mcp')
    os.environ.setdefault('GIGBID__portfolio__transport', 'stdio')
    os.environ.setdefault("LLM_BACKEND", "heuristic")
    from agent.config import load_config
    from mcp_servers.marketplace.adapters.sample import SampleAdapter
    from mcp_servers.portfolio.tools import PortfolioStore

    jobs = asyncio.run(SampleAdapter(CORPUS).search_jobs(limit=10000))
    store = PortfolioStore(CORPUS)
    if not jobs or not store.items or any("label" in j for j in jobs):
        raise SystemExit("Corpus loading or gold-label isolation check failed.")
    print(f"Loaded {len(jobs)} jobs and {len(store.items)} portfolio/proposal records from {CORPUS}")
    cfg = load_config()
    backend = os.environ.get("LLM_BACKEND") or cfg["llm"]["backend"]
    profile = cfg["llm"]["profile"]
    print(f"LLM backend: {backend}; profile: {profile}")
    if backend == "openai_compat":
        print("Models by node:", cfg["llm"]["profiles"][profile]["nodes"])
    if not args.check:
        import uvicorn

        configure_local_state(CORPUS.parents[2] / ".local-models/api-state")
        uvicorn.run("apps.api.main:create_app", factory=True, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
