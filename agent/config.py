from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path(__file__).with_name("config.yaml")


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def env_overrides(env=None) -> dict[str, Any]:
    """GIGBID__portfolio__source=mcp  ->  {"portfolio": {"source": "mcp"}}. Values are parsed as YAML."""
    out: dict[str, Any] = {}
    for k, v in (os.environ if env is None else env).items():
        if k.startswith("GIGBID__"):
            node, parts = out, k.removeprefix("GIGBID__").lower().split("__")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = yaml.safe_load(v)
    return out


def load_config(path: str | Path | None = None, overrides: dict[str, Any] | None = None) -> dict:
    cfg = yaml.safe_load(Path(path or DEFAULT_PATH).read_text())
    return _merge(_merge(copy.deepcopy(cfg), env_overrides()), overrides or {})
