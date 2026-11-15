"""Local GigSim-like simulator: the sample marketplace plus simulated clients with HIDDEN preferences.

Why it exists: the instructor's GigSim was not provided (TA: use public datasets + synthetic data). Replies/hires come from a
rule-based client model, so reply and hire RATES MEASURE ALIGNMENT WITH THIS MODEL'S ASSUMPTIONS, not real marketplace
behaviour. They are useful only for comparing configurations against each other. The preferences live in hidden_prefs.json and
are never returned by any tool.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any

from dataprep.clean import content_tokens
from dataprep.synth import ALIASES
from mcp_servers.marketplace.adapters.sample import DATA, SampleAdapter

GENERIC = re.compile(r"(?i)^(dear (sir|madam|hiring)|i am writing to|to whom it may concern)|perfect fit|best (freelancer|candidate)")


def _mentions(text: str, skill: str) -> bool:
    return any(re.search(r"(?<![\w+#.])" + re.escape(a) + r"(?![\w+#])", text, re.I) for a in {skill, *ALIASES.get(skill, [])})


class LocalSimAdapter(SampleAdapter):
    def __init__(self, data_dir: Path | str | None = None, connects: int = 10**6, seed: int = 7):
        d = Path(data_dir or DATA)
        super().__init__(d, connects)
        self._hidden: dict[str, dict] = json.loads((d / "hidden_prefs.json").read_text())
        self.seed = seed

    def reply_probability(self, key: str) -> float:
        d = self.drafts[key]["payload"]
        job, prefs = self._jobs[d["job_id"]], self._hidden[d["job_id"]]
        text = " ".join([d.get("cover_letter", ""), *d.get("screening_answers", [])])
        must = prefs["must_have"]
        mentioned = sum(_mentions(text, m) for m in must) / len(must) if must else 0.5
        ceil = prefs["budget_ceiling"]
        budget_ok = 1.0 if (ceil is None or d["bid_amount"] <= ceil) else 0.0
        title_tokens = set(content_tokens(job["title"]))
        personal = 1.0 if len(title_tokens & set(content_tokens(text))) >= 2 else 0.0
        generic = bool(GENERIC.search(d.get("cover_letter", "").strip()))
        p = 0.05 + 0.45 * mentioned + 0.15 * budget_ok + 0.15 * personal - (0.20 if prefs["dislikes_generic"] and generic else 0.0)
        return min(0.95, max(0.02, p))

    def outcome_for(self, key: str) -> dict[str, Any]:
        """Deterministic given (seed, key): reruns reproduce the same client decisions."""
        rng = random.Random(int(hashlib.sha256(f"{self.seed}|{key}".encode()).hexdigest()[:12], 16))
        p = self.reply_probability(key)
        replied = rng.random() < p
        interview = replied and rng.random() < 0.25 + 0.4 * p
        hired = interview and rng.random() < 0.35
        return {"p_reply": round(p, 3), "replied": replied, "interview": interview, "hired": hired}
