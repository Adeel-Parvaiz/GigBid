"""Exit 1 if unsupported claims rise or bid-or-skip F1 drops past thresholds (E2)."""
import json
import sys

import yaml

from evals.common import RESULTS, ROOT


def main() -> int:
    t = yaml.safe_load((ROOT / "evals/thresholds.yaml").read_text())
    d = json.loads((RESULTS / "decision_eval.json").read_text())
    i = json.loads((RESULTS / "injection_eval.json").read_text())
    checks = [
        ("bid_f1", d["base"]["bid_or_skip"]["f1"], ">=", t["bid_f1_min"]),
        ("scam_recall", d["base"]["scam_or_injection_detection"]["recall"], ">=", t["scam_recall_min"]),
        ("unsupported_after", d["fabricating_writer_verifier_on"]["unsupported_claims_per_proposal_after"], "<=", t["unsupported_claims_after_max"]),
        ("injection_asr_on", i["known_patterns"]["defence_on"]["attack_success_rate"], "<=", t["injection_asr_defence_on_max"]),
    ]
    bad = 0
    for name, val, op, lim in checks:
        ok = val >= lim if op == ">=" else val <= lim
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'} {name}: {val} {op} {lim}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
