"""One-at-a-time ablation of the shipped pipeline on the decision metrics. python -m evals.runners.ablation"""
from __future__ import annotations

import asyncio

from evals.common import write_result
from evals.runners.decision_eval import FabricatingWriter, run

CASES = {"full": ({}, None),
         "no_risk_rule_floor": ({"defences": {"risk_rule_floor": False}}, None),
         "no_claim_verification(fabricating writer)": ({"defences": {"verify_claims": False}}, FabricatingWriter()),
         "full(fabricating writer)": ({}, FabricatingWriter()),
         "rag_v0_instead_of_v1": ({"rag": {"variant": "v0_naive"}}, None)}


async def main():
    out = {}
    for name, (over, llm) in CASES.items():
        r = await run(over, llm)
        out[name] = {"bid_f1": r["bid_or_skip"]["f1"], "scam_recall": r["scam_or_injection_detection"]["recall"],
                     "unsupported_after": r["unsupported_claims_per_proposal_after"]}
    return out


if __name__ == "__main__":
    print(write_result("ablation", {"cases": asyncio.run(main())}))
