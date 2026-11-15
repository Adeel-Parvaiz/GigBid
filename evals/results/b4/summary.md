# B4 evaluation results

- Scope: `full_protocol`; 16/1200 planned runs.
- Full assignment protocol complete: **False**.
- Human calibration: n=30, agreement=36.7%, Cohen's κ=0.000 (calibration_measured).
- Blind panel: pending_classmates (0 classmate raters).

| Variant | Persona | Attempted | Errors | Bid/skip F1 | Scam P / R | Price in band | Unsupported / proposal | Judge mean / n | Reply / hire (submitted) | Analysis p95 s | Proposal p95 s | Tokens / proposal | API USD / proposal |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v0_naive | ai-ml-engineer | 3 | 1 | 0.667 | n/a / n/a | 100.0% (n=1) | 0.000 | n/a / 0 | n/a / n/a | 30.89 | 12.69 | 8070.0 | 0.0000 |
| v0_naive | data-analyst | 2 | 0 | 1.000 | n/a / n/a | 100.0% (n=2) | 0.000 | n/a / 0 | 100.0% / 0.0% | 31.96 | 29.02 | 16924.0 | 0.0000 |
| v0_naive | fullstack-dev | 3 | 0 | 1.000 | n/a / n/a | 100.0% (n=3) | 0.000 | n/a / 0 | 33.3% / 33.3% | 31.92 | 28.48 | 17969.3 | 0.0000 |
| v8_corrective | ai-ml-engineer | 3 | 0 | 0.800 | n/a / n/a | 100.0% (n=2) | 0.000 | n/a / 0 | 50.0% / 0.0% | 29.12 | 25.23 | 16304.5 | 0.0000 |
| v8_corrective | data-analyst | 2 | 0 | 1.000 | n/a / n/a | 100.0% (n=2) | 0.000 | n/a / 0 | 100.0% / 100.0% | 22.99 | 19.44 | 10636.0 | 0.0000 |
| v8_corrective | fullstack-dev | 3 | 0 | 1.000 | n/a / n/a | 100.0% (n=3) | 0.000 | n/a / 0 | 0.0% / 0.0% | 38.48 | 32.00 | 19453.0 | 0.0000 |

- Cost basis: Actual local inference API charges only. Hardware/electricity not measured.
- Outcome scope: Project-owned rule-based GigSim only. Rates are not real hiring outcomes. Only draft-ID-matched outcomes count.
- The development jobs and gold labels are synthetic. Simulator reply/hire rates are not marketplace outcomes.
- The judge showed no agreement beyond chance on this calibration set; its rubric scores are not calibrated.
- B4 requires the full protocol and the classmate panel. Exploratory sampling or pending human ratings do not satisfy that completion gate.
