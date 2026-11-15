"""Regenerate the B3 report from saved real-model drafts and verification traces."""
import json
from pathlib import Path

from evals.rd_b.verify_claims_real import summarize

ROOT = Path(__file__).resolve().parents[2]


def percentage(value):
    return 'n/a (no retained claims)' if value is None else f'{value:.1%}'


def main():
    folder = ROOT / 'evals/results/b3'
    report = json.loads((folder / 'summary.json').read_text())
    rows = [json.loads(line) for line in (folder / 'proposals.jsonl').read_text().splitlines()]
    assert len(rows) == 12 and len({(r['persona'], r['job_id']) for r in rows}) == 12
    report['all'] = summarize(rows)
    report['per_persona'] = {p: summarize([r for r in rows if r['persona'] == p])
                             for p in ['ai-ml-engineer', 'fullstack-dev', 'data-analyst']}
    (folder / 'summary.json').write_text(json.dumps(report, indent=2))
    lines = ['# B3 — Claim verification before the Critic', '',
             'B3 is implemented: proposals are split into sentence-level claims, checked against retrieved evidence, '
             'and filtered before the Critic receives the draft. Unsupported **and partly supported** claims are removed. '
             'No automatic rewrite invents a replacement fact. Empty drafts remain blocked by the existing Critic/compliance/approval gates.', '',
             '## Real-model before/after measurement', '',
             'Twelve ordinary synthetic development jobs, four per persona, were drafted with the configured local Qwen model. '
             'Jobs and evidence were fetched through official SDK MCP clients; the actual Writer, Verifier and Critic node functions were executed '
             'in that order. No proposals were submitted. The same twelve development jobs were reused while fixing defects, so this is an '
             'iterative development measurement, not an unbiased held-out test.', '',
             '| Persona | Drafts | Sentence units before / after | Unsupported before | Before rate | Unsupported after repeat check | After rate | Empty cleaned drafts |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for persona, metrics in [*report['per_persona'].items(), ('All', report['all'])]:
        lines.append(f'| {persona} | {metrics["proposals"]} | {metrics["claims_before"]} / {metrics["claims_after"]} | '
                     f'{metrics["unsupported_before"]} | {percentage(metrics["unsupported_rate_before"])} | '
                     f'{metrics["unsupported_after_rechecked"]} | {percentage(metrics["unsupported_rate_after"])} | '
                     f'{metrics["empty_clean_drafts"]} |')
    metrics = report['all']
    lines += ['', f'Unsupported sentence units per proposal: **{metrics["unsupported_per_proposal_before"]:.3f} before**, '
              f'**{metrics["unsupported_per_proposal_after"]:.3f} after**. '
              f'Partly supported units before filtering: **{metrics["partly_supported_before"]}**. '
              f'Claim retention: **{percentage(metrics["retained_claim_fraction"])}**.', '',
              'Rates count normalized cover-letter and screening-answer sentence units, including nonfactual boilerplate. '
              'A missing citation/quote can cause an unsupported label; this rate is not a human-measured hallucination rate. '
              'Zero retained claims yields an undefined after-rate, reported as n/a, not a misleading 0%. '
              'A low unsupported count obtained by deleting useful text does not demonstrate good proposal quality.', '',
              '## Verification behavior', '',
              '- Compound claims are split on sentence boundaries, newlines and semicolons. Citation IDs, claim kind and screening section are preserved.',
              '- Experience hidden under a boilerplate label is still checked. Model-authored logistics are removed upstream; actual calendar logistics retain the existing code-built path.',
              '- Missing/unknown citations cannot fall back to arbitrary evidence. One cited source must establish each factual claim; unrelated evidence fragments are not concatenated into apparent support.',
              '- Deterministic guards reject fabricated whole numbers/percentages, absent named organizations, unestablished qualification levels and extra accomplishments. These conservative rules can also reject valid paraphrases.',
              '- With `verification.backend=auto`, a real `OpenAICompatLLM` additionally runs the semantic prompt. '
              'The schema requires a real citation ID and an exact source passage for supported/partly supported decisions. '
              'Claim indices and source IDs/passages are constrained to supplied values. Missing/duplicate verdicts or invalid quotes fail closed.',
              '- Survivors are checked again and any downgraded claims are removed before Critic. The graph already routes Writer → Verifier → Critic; every revision repeats verification.',
              '- Human-edited cover letters are rechecked before approval and blocked when unsupported; a separate edited-cover field cannot override the filtered claim list.',
              '- `rules` is the explicitly labeled offline verifier. `llm` forces semantic checks. In `auto`, offline test doubles use rules; real-model checks never silently fall back after a model failure. '
              'The verifier inherits the configured Writer model unless a `claim_verifier` model is configured in the active profile.', '',
              '## Synthetic controls and pilot failures', '',
              'Controls are authored, deliberately injected examples with labels established by construction, not human annotation or judge calibration. '
              'They are excluded from the natural-draft rates above.', '',
              '| Control | Expected | Observed |', '|---|---|---|']
    for control in report['synthetic_controls']:
        lines.append(f'| {control["name"]} | {control["expected_synthetic_label"]} | {control["actual"]} |')
    lines += ['', 'The initial pilot found a semantic verdict that changed on a repeat check. A subsequent positive control exposed '
              'optional citation/quote schema fields: the small model omitted those fields, causing even a valid source sentence to be rejected. '
              'Survivor rechecking and mandatory source fields address those concrete defects. Both pilot artifacts are retained under '
              '`evals/results/b3/pilot/`; failed runs are not presented as successful final measurements.', '',
              '## Limits and reproduction', '',
              'The verifier is evidence-conditioned, not an independent fact checker. Source authorship/outcomes may be user-reported or synthetic. '
              'The Writer and semantic checker use the same small model; repeat agreement is not independent human ground truth, and exact quotes '
              'alone do not prove entailment. Semantic labels remain uncalibrated. B4\'s 30 human labels, Cohen\'s kappa, calibrated rubric judge '
              'and blind classmate panel remain separate requirements. Extra verification calls add latency/token use; every returned provider usage '
              'object for this run is saved in the summary.', '',
              '```bash', 'python -m evals.rd_b.verify_claims_real', 'python -m evals.rd_b.report_claims', '```', '',
              'Evidence: [per-draft text, retrieved evidence and verdicts](../evals/results/b3/proposals.jsonl), '
              '[metrics, controls and raw model responses/usage](../evals/results/b3/summary.json), '
              '[test evidence](../evals/results/b3_validation.json).', '',
              'Code: `rag/verify.py`, `agent/nodes/verifier.py`, `agent/nodes/compliance.py`, '
              '`agent/prompts/claim_verifier.md`; regressions in `tests/unit/test_b3_verification.py`.', '']
    (ROOT / 'docs/CLAIM_VERIFICATION.md').write_text('\n'.join(lines))
    print(json.dumps(report['all'], indent=2))


if __name__ == '__main__':
    main()
