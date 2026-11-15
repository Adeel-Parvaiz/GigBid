"""Cohen's kappa between your own labels and the LLM judge. Input JSON: [{"id":..,"human":"good","judge":"bad"}, ...] (>=30 items)."""
from __future__ import annotations

import json
import sys

from evals.common import write_result
from evals.metrics import cohen_kappa


def calibrate(items: list[dict]) -> dict:
    h, j = [i["human"] for i in items], [i["judge"] for i in items]
    k = cohen_kappa(h, j)
    return {"n": len(items), "kappa": round(k, 3), "agreement": round(sum(a == b for a, b in zip(h, j, strict=True)) / len(items), 3),
            "meets_30_item_requirement": len(items) >= 30,
            "disagreements": [i for i in items if i["human"] != i["judge"]]}


if __name__ == "__main__":
    print(write_result("judge_calibration", calibrate(json.load(open(sys.argv[1]))), corpus="your-30-labels", llm="your-judge"))
