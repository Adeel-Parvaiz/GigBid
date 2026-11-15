"""Explicit promotion rules. Raw tool output / single edits never enter long-term memory.

Style: a signal derived from the user's edit diff is only promoted after it recurs in N DISTINCT jobs.
Outcome: per-category stats are only exposed once a category has >= min_samples outcomes.
"""
from __future__ import annotations

import re

_SENT = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text.strip()) if s.strip()]


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z'-]+", text.lower()) if len(w) >= 5}


def extract_signals(original: str, edited: str) -> list[str]:
    """Candidate style signals from one edit. Full rewrites carry no style signal and are ignored."""
    o, e = sentences(original), sentences(edited)
    if not o or not e:
        return []
    kept = sum(1 for s in o if s in e) / len(o)
    if kept < 0.5:
        return []
    sigs = []
    if o[0] not in e:
        sigs.append("cut_first_sentence")
    sigs += [f"avoid_word:{w}" for w in sorted(words(original) - words(edited))]
    return sigs


def rule_text(signal: str) -> str:
    if signal == "cut_first_sentence":
        return "Do not open with a pleasantry or restatement; start with the substance."
    if signal.startswith("avoid_word:"):
        return f"Never use the word '{signal.split(':', 1)[1]}'."
    return signal
