from __future__ import annotations

import math
import statistics


def recall_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    return len(set(ranked[:k]) & gold) / len(gold) if gold else float("nan")


def mrr(ranked: list[str], gold: set[str]) -> float:
    for i, r in enumerate(ranked, 1):
        if r in gold:
            return 1 / i
    return 0.0


def ndcg_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    dcg = sum(1 / math.log2(i + 1) for i, r in enumerate(ranked[:k], 1) if r in gold)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(gold), k) + 1))
    return dcg / ideal if ideal else float("nan")


def prf(pred: list[bool], gold: list[bool]) -> dict[str, float]:
    tp = sum(p and g for p, g in zip(pred, gold, strict=True))
    fp = sum(p and not g for p, g in zip(pred, gold, strict=True))
    fn = sum(g and not p for p, g in zip(pred, gold, strict=True))
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * p * r / (p + r) if tp else (0.0 if tp + fp + fn else float("nan"))
    return {"precision": p, "recall": r, "f1": f1}


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def percentile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, math.ceil(q * len(xs)) - 1)]


def mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if not math.isnan(x)]
    return round(statistics.fmean(xs), 4) if xs else None


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% interval for a rate. Report it: with small n the interval is wide and differences are noise."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)
