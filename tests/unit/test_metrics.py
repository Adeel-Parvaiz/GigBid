import math

import pytest

from evals.metrics import cohen_kappa, mrr, ndcg_at_k, percentile, prf, recall_at_k


def test_ranking_metrics_hand_computed():
    ranked, gold = ["a", "b", "c", "d"], {"c", "z"}
    assert recall_at_k(ranked, gold, 5) == 0.5 and recall_at_k(ranked, gold, 2) == 0.0
    assert mrr(ranked, gold) == pytest.approx(1 / 3)
    # DCG = 1/log2(4) = 0.5 ; ideal (2 gold) = 1 + 1/log2(3) = 1.6309
    assert ndcg_at_k(ranked, gold, 10) == pytest.approx(0.5 / (1 + 1 / math.log2(3)))
    assert ndcg_at_k(["c", "z"], gold, 10) == pytest.approx(1.0)


def test_prf_and_kappa_and_percentile():
    r = prf([True, True, False, False], [True, False, True, False])
    assert r == {"precision": 0.5, "recall": 0.5, "f1": 0.5}
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "a", "b", "b"]) == 1.0
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == pytest.approx(0.0)
    assert cohen_kappa(list("aaabbb"), list("aabbbb")) == pytest.approx(0.6667, abs=1e-3)   # po=5/6, pe=.5
    assert percentile(list(range(1, 101)), .95) == 95
