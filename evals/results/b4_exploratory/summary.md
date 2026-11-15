# B4 evaluation results

- Scope: `exploratory_random_per_persona`; 300/300 planned runs.
- Full assignment protocol complete: **False**.
- Human calibration: n=30, agreement=36.7%, Cohen's κ=0.000 (calibration_measured).
- Blind panel: pending_classmates (0 classmate raters).

| Variant | Persona | Attempted | Errors | Bid/skip F1 | Scam P / R | Price in band | Unsupported / proposal | Judge mean / n | Reply / hire (submitted) | Analysis p95 s | Proposal p95 s | Tokens / proposal | API USD / proposal |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v0_naive | ai-ml-engineer | 50 | 0 | 0.824 | 100.0% / 37.5% | 100.0% (n=14) | 0.000 | 3.000 / 14 | 50.0% / 10.0% | 38.09 | 38.33 | 15823.1 | 0.0000 |
| v0_naive | data-analyst | 50 | 0 | 0.889 | 100.0% / 28.6% | 87.5% (n=16) | 0.000 | 3.000 / 16 | 57.1% / 14.3% | 42.34 | 48.59 | 17560.2 | 0.0000 |
| v0_naive | fullstack-dev | 50 | 2 | 0.857 | 100.0% / 25.0% | 93.3% (n=15) | 0.000 | 3.000 / 15 | 38.5% / 7.7% | 43.27 | 39.04 | 16980.7 | 0.0000 |
| v8_corrective | ai-ml-engineer | 50 | 1 | 0.848 | 100.0% / 37.5% | 100.0% (n=14) | 0.000 | 3.000 / 14 | 57.1% / 0.0% | 33.35 | 35.10 | 13352.6 | 0.0000 |
| v8_corrective | data-analyst | 50 | 1 | 0.944 | 100.0% / 28.6% | 88.2% (n=17) | 0.000 | 2.824 / 17 | 46.2% / 15.4% | 48.51 | 50.79 | 15758.6 | 0.0000 |
| v8_corrective | fullstack-dev | 50 | 1 | 0.923 | 100.0% / 25.0% | 94.7% (n=19) | 0.000 | 3.000 / 19 | 46.7% / 13.3% | 46.68 | 47.43 | 13889.3 | 0.0000 |

- Cost basis: Actual local inference API charges only. Hardware/electricity not measured.
- Outcome scope: Project-owned rule-based GigSim only. Rates are not real hiring outcomes. Only draft-ID-matched outcomes count.
- The development jobs and gold labels are synthetic. Simulator reply/hire rates are not marketplace outcomes.
- The judge showed no agreement beyond chance on this calibration set; its rubric scores are not calibrated.
- B4 requires the full protocol and the classmate panel. Exploratory sampling or pending human ratings do not satisfy that completion gate.
