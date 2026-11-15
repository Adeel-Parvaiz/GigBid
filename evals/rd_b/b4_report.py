"""B4 metrics and honest completion gates; stdlib only, no inferred human ratings."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from evals.metrics import wilson
from evals.rd_b.review_data import calibration, digest, panel_summary

ROOT = Path(__file__).resolve().parents[2]


def average(values):
    return statistics.fmean(values) if values else None


def quantile(values, q):
    return sorted(values)[max(0, math.ceil(len(values) * q) - 1)] if values else None


def prf(predicted, gold):
    tp = sum(a and b for a, b in zip(predicted, gold, strict=True))
    fp = sum(a and not b for a, b in zip(predicted, gold, strict=True))
    fn = sum(not a and b for a, b in zip(predicted, gold, strict=True))
    return {'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}


def summarize(rows):
    complete = [r for r in rows if r.get('decision') and not r.get('error')]
    priced = [r for r in complete if r.get('price') and r['gold'].get('price_band')]
    proposals = [r for r in complete if r.get('proposal') is not None]
    submissions = [r for r in rows if r.get('submitted')]
    verified = [r for r in submissions if r.get('outcome') and r.get('outcome_match') == 'draft_id']
    outcomes_complete = len(verified) == len(submissions)
    def calls_for_proposal(row):
        return [c for c in row.get('calls', []) if c['node'] in {'writer', 'claim_verifier', 'critic'}]
    return {'attempted': len(rows), 'decision_completed': len(complete), 'errors': len(rows) - len(complete),
        'bid_or_skip': prf([r['decision']['action'] == 'bid' for r in complete], [r['gold']['gold_action'] == 'bid' for r in complete]),
        'scam_detection': prf([bool(set((r.get('risk') or {}).get('flags', [])) & {'unpaid_work', 'off_platform_contact'}) for r in complete],
                              [bool(r['gold'].get('scam')) for r in complete]),
        'injection_detection': prf(['prompt_injection' in (r.get('risk') or {}).get('flags', []) for r in complete],
                                  [bool(r['gold'].get('injection')) for r in complete]),
        'price_in_fair_band': {'eligible': len(priced), 'rate': average([r['gold']['price_band'][0] <= r['price']['amount'] <= r['gold']['price_band'][1] for r in priced])},
        'proposals': len(proposals), 'empty_proposals': sum(not r['proposal'].get('cover_letter', '').strip() for r in proposals),
        'unsupported_per_proposal': average([(r.get('verification') or {}).get('unsupported_after', 0) for r in proposals]),
        'submitted': len(submissions), 'outcomes_verified': len(verified),
        'reply_rate_submitted': average([r['outcome']['replied'] for r in verified]),
        'hire_rate_submitted': average([r['outcome']['hired'] for r in verified]),
        'reply_rate_submitted_95ci': wilson(sum(r['outcome']['replied'] for r in verified), len(verified)),
        'hire_rate_submitted_95ci': wilson(sum(r['outcome']['hired'] for r in verified), len(verified)),
        'reply_rate_attempted': sum(r['outcome']['replied'] for r in verified) / len(rows) if rows and outcomes_complete else None,
        'hire_rate_attempted': sum(r['outcome']['hired'] for r in verified) / len(rows) if rows and outcomes_complete else None,
        'analysis_p50_seconds': quantile([r['analysis_seconds'] for r in rows], .5),
        'analysis_p95_seconds': quantile([r['analysis_seconds'] for r in rows], .95),
        'analysis_mean_tokens': average([r['tokens'] for r in rows if r.get('tokens_complete')]),
        'proposal_pipeline_p50_seconds': quantile([sum(c['seconds'] for c in calls_for_proposal(r)) for r in proposals], .5),
        'proposal_pipeline_p95_seconds': quantile([sum(c['seconds'] for c in calls_for_proposal(r)) for r in proposals], .95),
        'proposal_pipeline_mean_tokens': average([sum((c.get('prompt_tokens') or 0) + (c.get('completion_tokens') or 0) for c in calls_for_proposal(r)) for r in proposals if r.get('tokens_complete')]),
        'billed_api_usd_per_job': average([r['billed_api_usd'] for r in rows]),
        'billed_api_usd_per_proposal': average([r['billed_api_usd'] for r in proposals]),
        'hardware_usd': None}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def render_markdown(result):
    def percent(value):
        return 'n/a' if value is None else f'{value * 100:.1f}%'

    def number(value, digits=3):
        return 'n/a' if value is None else f'{value:.{digits}f}'

    kappa_value = result['calibration'].get('kappa')
    if kappa_value is None:
        calibration_note = "Cohen's κ is undefined for the collected labels."
    elif kappa_value <= 0:
        calibration_note = "The judge showed no agreement beyond chance on this calibration set; its rubric scores are not calibrated."
    else:
        calibration_note = "Cohen's κ is positive; no minimum acceptance threshold was specified."
    lines = [
        '# B4 evaluation results',
        '',
        f"- Scope: `{result['evaluation_scope']}`; {result['completed_runs']}/{result['planned_runs']} planned runs.",
        f"- Full assignment protocol complete: **{result['full_protocol_complete']}**.",
        f"- Human calibration: n={result['calibration'].get('n', 0)}, agreement="
        f"{percent(result['calibration'].get('agreement'))}, Cohen's κ="
        f"{number(result['calibration'].get('kappa'))} ({result['calibration']['status']}).",
        f"- Blind panel: {result['panel']['status']} ({result['panel']['raters']} classmate raters).",
        '',
        '| Variant | Persona | Attempted | Errors | Bid/skip F1 | Scam P / R | Price in band | Unsupported / proposal | Judge mean / n | Reply / hire (submitted) | Analysis p95 s | Proposal p95 s | Tokens / proposal | API USD / proposal |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for key, metrics in sorted(result['metrics'].items()):
        variant, persona = key.split('/', 1)
        scam = metrics['scam_detection']
        price = metrics['price_in_fair_band']
        judge = metrics['judge_score']
        lines.append(
            f"| {variant} | {persona} | {metrics['attempted']} | {metrics['errors']} "
            f"| {number(metrics['bid_or_skip']['f1'])} "
            f"| {percent(scam['precision'])} / {percent(scam['recall'])} "
            f"| {percent(price['rate'])} (n={price['eligible']}) "
            f"| {number(metrics['unsupported_per_proposal'])} "
            f"| {number(judge['mean_overall'])} / {judge['scored']} "
            f"| {percent(metrics['reply_rate_submitted'])} / {percent(metrics['hire_rate_submitted'])} "
            f"| {number(metrics['analysis_p95_seconds'], 2)} "
            f"| {number(metrics['proposal_pipeline_p95_seconds'], 2)} "
            f"| {number(metrics['proposal_pipeline_mean_tokens'], 1)} "
            f"| {number(metrics['billed_api_usd_per_proposal'], 4)} |"
        )
    lines.extend([
        '',
        f"- Cost basis: {result['cost_note']}",
        f"- Outcome scope: {result['outcome_note']}",
        '- The development jobs and gold labels are synthetic. Simulator reply/hire rates are not marketplace outcomes.',
        f'- {calibration_note}',
        '- B4 requires the full protocol and the classmate panel. Exploratory sampling or pending human ratings do not satisfy that completion gate.',
        '',
    ])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration-ratings', type=Path,
                        help='Use this author rating file without replacing saved review records')
    parser.add_argument('--results-dir', type=Path, default=Path('evals/results/b4'),
                        help='Evaluation output directory')
    parser.add_argument('--review-dir', type=Path, default=Path('evals/reviews/b4'),
                        help='Human review pack directory')
    args = parser.parse_args()
    folder = args.results_dir if args.results_dir.is_absolute() else ROOT / args.results_dir
    review_dir = args.review_dir if args.review_dir.is_absolute() else ROOT / args.review_dir
    folder.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(folder / 'runs.jsonl')
    sidecar = folder / 'outcomes_reconciled.json'
    if sidecar.exists():
        verified_outcomes = json.loads(sidecar.read_text())['outcomes']
        for row in rows:
            key = row['variant'] + '/' + str((row.get('submission') or {}).get('draft_id'))
            if row.get('submitted') and key in verified_outcomes:
                row['outcome'], row['outcome_match'] = verified_outcomes[key], 'draft_id'
    if len({(r['variant'], r['persona'], r['job_id']) for r in rows}) != len(rows):
        raise ValueError('Duplicate evaluation runs must be reconciled before reporting')
    groups = defaultdict(list)
    for row in rows:
        groups[row['variant'], row['persona']].append(row)
    manifest_path = folder / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    planned_runs = manifest.get('planned_graph_runs', 1200)
    sample_mode = manifest.get('sample_mode', 'full_protocol')
    full_protocol_complete = sample_mode == 'full_protocol' and planned_runs == 1200 and len(rows) == planned_runs
    result = {'evaluation_scope': sample_mode,
              'full_protocol_complete': full_protocol_complete,
              'automated_run_status': 'complete' if len(rows) == planned_runs else 'incomplete',
              'runs_import_status': 'present' if (folder / 'runs.jsonl').exists() else 'not_available_in_this_checkout',
              'completed_runs': len(rows), 'planned_runs': planned_runs,
              'metrics': {f'{v}/{p}': summarize(part) for (v, p), part in groups.items()},
              'calibration': {'status': 'pending_author_30_labels'},
              'panel': {'status': 'pending_classmates', 'raters': 0},
              'cost_note': 'Actual local inference API charges only. Hardware/electricity not measured.',
              'outcome_note': 'Project-owned rule-based GigSim only. Rates are not real hiring outcomes. Only draft-ID-matched outcomes count.'}
    retrieval = ROOT / 'evals/results/b2/summary.json'
    if retrieval.exists():
        b2 = json.loads(retrieval.read_text())
        result['retrieval'] = {'source': 'measured B2 real-neural full-dev comparison',
            'scores': [r for r in b2['scores'] if r['variant'] in {'v0_naive', 'v8_corrective'}]}
    ratings = ROOT / '.local-models/b4-reviews'
    calibration_pack = review_dir / 'calibration.json'
    if args.calibration_ratings:
        rating_path = args.calibration_ratings
        if not rating_path.is_absolute():
            rating_path = ROOT / rating_path
        author = [rating_path]
    else:
        author = list(ratings.glob('calibration-*.json')) if ratings.exists() else []
    calibration_predictions = folder / 'judge_calibration_predictions.jsonl'
    if not calibration_predictions.exists():
        # Calibration uses a fixed pack shared by full and exploratory runs.
        calibration_predictions = ROOT / 'evals/results/b4/judge_calibration_predictions.jsonl'
    predictions = read_jsonl(calibration_predictions)
    if author and calibration_pack.exists() and len(predictions) == 30:
        if len(author) != 1:
            raise ValueError('Select exactly one actual assignment-author calibration file')
        result['calibration'] = calibration(json.loads(calibration_pack.read_text()), json.loads(author[0].read_text()), predictions)
    panel_pack = review_dir / 'panel.json'
    panel_key = ratings / 'panel_key.json'
    if panel_pack.exists() and panel_key.exists():
        classmates = [json.loads(path.read_text()) for path in ratings.glob('panel-*.json')]
        if author and any(r['reviewer'].casefold() == json.loads(author[0].read_text())['reviewer'].casefold() for r in classmates):
            raise ValueError('The author cannot also count as a classmate panel member')
        result['panel'] = panel_summary(json.loads(panel_pack.read_text()),
            classmates, json.loads(panel_key.read_text()))
    rubric = {r['id']: r for r in read_jsonl(folder / 'judge_proposal_predictions.jsonl')}
    eligible = [r for r in rows if r.get('proposal') is not None]
    scored = [rubric[digest([r['persona'], r['job_id'], r['variant']])] for r in eligible
              if digest([r['persona'], r['job_id'], r['variant']]) in rubric]
    result['proposal_rubric'] = {'eligible': len(eligible), 'scored': len(scored),
        'mean_overall': average([r['overall'] for r in scored]),
        'calibration_status': result['calibration']['status']}
    for group, metrics in result['metrics'].items():
        variant, persona = group.split('/')
        selected = [rubric[digest([r['persona'], r['job_id'], r['variant']])] for r in eligible
                    if r['persona'] == persona and r['variant'] == variant and digest([r['persona'], r['job_id'], r['variant']]) in rubric]
        metrics['judge_score'] = {'mean_overall': average([r['overall'] for r in selected]), 'scored': len(selected),
                                  'calibration_status': result['calibration']['status']}
    outcomes_ready = all(m['submitted'] == m['outcomes_verified'] for m in result['metrics'].values())
    result['B4_complete'] = (full_protocol_complete and result['automated_run_status'] == 'complete' and
        outcomes_ready and len(result['metrics']) == 6 and all(m['decision_completed'] > 0 for m in result['metrics'].values()) and
        len(scored) == len(eligible) and bool(scored) and
        result['calibration']['status'] == 'calibration_measured' and result['panel']['status'] == 'collected')
    (folder / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False))
    (folder / 'summary.md').write_text(render_markdown(result), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['completed_runs', 'planned_runs', 'calibration', 'panel', 'B4_complete']}, indent=2))


if __name__ == '__main__':
    main()
