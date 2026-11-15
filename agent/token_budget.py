from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field


class TokenBudgetExceeded(RuntimeError):
    pass


def estimate_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


@dataclass
class TokenBudget:
    limit: int
    used_before: int
    node: str
    used_here: int = 0
    usage: list[dict] = field(default_factory=list)

    @property
    def total_used(self) -> int:
        return self.used_before + self.used_here

    def output_limit(self, prompt: str) -> int:
        prompt_tokens = estimate_tokens(prompt)
        remaining = self.limit - self.total_used
        if prompt_tokens >= remaining:
            raise TokenBudgetExceeded(
                f"token budget {self.limit} cannot fit the next prompt at {self.node} "
                f"(used {self.total_used}, estimated prompt {prompt_tokens})"
            )
        return remaining - prompt_tokens

    def record(self, tokens: int) -> None:
        self.used_here += max(0, int(tokens))

    def record_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float,
        exact_usage: bool,
        total_tokens: int | None = None,
    ) -> None:
        self.usage.append({
            "model": model,
            "input_tokens": max(0, int(input_tokens)),
            "output_tokens": max(0, int(output_tokens)),
            "total_tokens": max(0, int(total_tokens if total_tokens is not None else input_tokens + output_tokens)),
            "duration_seconds": max(0.0, float(duration_seconds)),
            "exact_usage": exact_usage,
        })


current_token_budget: ContextVar[TokenBudget | None] = ContextVar("gigbid_token_budget", default=None)
