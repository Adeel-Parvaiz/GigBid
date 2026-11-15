from __future__ import annotations

import httpx
from langgraph.types import RetryPolicy

from agent.marketplace_port import MarketplaceError


def retryable_node_error(error: Exception) -> bool:
    if isinstance(error, BaseExceptionGroup):
        return bool(error.exceptions) and all(retryable_node_error(exc) for exc in error.exceptions)
    if isinstance(error, MarketplaceError):
        return error.code == "rate_limited"
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {408, 429, 500, 502, 503, 504}
    return isinstance(error, (TimeoutError, ConnectionError, OSError, httpx.TransportError))


def node_runtime_options(cfg: dict, node: str) -> dict:
    resilience = cfg.get("resilience", {})
    defaults = resilience.get("defaults", {})
    policy = resilience.get("nodes", {}).get(node, {})
    timeout = float(policy.get("timeout_seconds", defaults.get("timeout_seconds", 45)))
    attempts = int(policy.get("max_attempts", defaults.get("max_attempts", 3)))
    initial_interval = float(defaults.get("retry_initial_interval_seconds", 0.25))
    max_interval = float(defaults.get("retry_max_interval_seconds", 2))
    if timeout <= 0 or attempts < 1 or initial_interval < 0 or max_interval < initial_interval:
        raise ValueError(f"invalid resilience policy for node {node!r}")
    return {
        "timeout_seconds": timeout,
        "retry_policy": RetryPolicy(
            initial_interval=initial_interval,
            backoff_factor=2,
            max_interval=max_interval,
            max_attempts=attempts,
            jitter=False,
            retry_on=retryable_node_error,
        ),
    }
