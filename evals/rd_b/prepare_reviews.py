"""Prepare genuine unlabeled human-review forms; never create human answers."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from evals.rd_b.review_data import digest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'evals/reviews/b4'


def make_packs(results_dir: Path | None = None):
    rows = [json.loads(line) for line in (ROOT / 'evals/results/b3/proposals.jsonl').read_text().splitlines()]
    jobs = {j['job_id']: j for j in json.loads((ROOT / 'data/processed/kaggle_2024_v1/jobs.json').read_text())}
    items, private = [], {}
    for row in rows:
        for phase in ('original', 'clean'):
            draft = row[phase]
            eid = 'item-' + digest([row['persona'], row['job_id'], phase])[:12]
            items.append({'id': eid, 'job': jobs[row['job_id']],
                          'proposal': draft['cover_letter'], 'screening_answers': draft.get('screening_answers', []),
                          'evidence': row['evidence']})
            private[eid] = {'persona': row['persona'], 'job_id': row['job_id'], 'phase': phase, 'source': 'real-model-B3'}
    # Six transparent reference stimuli broaden calibration, not measured agent outcome results.
    for row in rows[::2]:
        source = row['evidence'][0]
        eid = 'reference-' + digest([row['persona'], row['job_id']])[:12]
        text = (f'Relevant portfolio work: {source["summary"]}\n\n'
                'I will first confirm the data, acceptance criteria and scope with you, then implement a reproducible baseline, '
                'compare alternatives against agreed metrics and document the limitations. '
                'Could you share a representative sample and your highest-priority deliverable?')
        items.append({'id': eid, 'job': jobs[row['job_id']], 'proposal': text, 'screening_answers': [], 'evidence': [source]})
        private[eid] = {'persona': row['persona'], 'job_id': row['job_id'], 'phase': 'reference', 'source': 'code-generated grounded reference, not model output'}
    assert len(items) == 30
    random.Random(4016).shuffle(items)
    pack = {'kind': 'calibration', 'rubric': {
        '0': 'Unusable: empty, misleading, unsafe or no meaningful response to the job.',
        '1': 'Poor: major grounding, relevance or completeness problems.',
        '2': 'Mixed: partly useful, but substantial edits needed.',
        '3': 'Good: relevant, grounded and clear; only minor edits needed.',
        '4': 'Excellent: specific evidence, a credible plan, complete answers and professional wording.'},
        'instructions': 'Personally read all 30 items and source evidence. Give an overall quality score, 0–4. Do not consult model scores. Unknown job details must not be inferred.',
        'scope': '24 actual B3 draft/filtered items and six code-generated grounded reference stimuli. Synthetic jobs/evidence. No labels are prefilled.',
        'items': items}
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'calibration.json').exists() and json.loads((OUT / 'calibration.json').read_text()) != pack:
        raise ValueError('A frozen review pack already exists; do not invalidate collected human ratings')
    (OUT / 'calibration.json').write_text(json.dumps(pack, indent=2))
    key = ROOT / '.local-models/b4-reviews'
    key.mkdir(parents=True, exist_ok=True)
    (key / 'calibration_key.json').write_text(json.dumps(private, indent=2))
    print('30 unlabeled calibration items ready')
    runs_path = (results_dir or ROOT / 'evals/results/b4') / 'runs.jsonl'
    if runs_path.exists():
        runs = [json.loads(line) for line in runs_path.read_text().splitlines()]
        pairs, pair_key = [], {}
        rng = random.Random(4016)
        for persona in ['ai-ml-engineer', 'fullstack-dev', 'data-analyst']:
            groups = {}
            for row in runs:
                if row['persona'] == persona and row.get('gold', {}).get('gold_action') == 'bid' and row['job_id'].startswith('syn-'):
                    groups.setdefault(row['job_id'], {})[row['variant']] = row
            chosen = [(job, entries) for job, entries in sorted(groups.items()) if len(entries) == 2][:5]
            for job, entries in chosen:
                variants = ['v0_naive', 'v8_corrective']
                rng.shuffle(variants)
                eid = 'pair-' + digest([persona, job])[:12]
                a, b = [entries[v] for v in variants]
                pairs.append({'id': eid, 'job': a.get('job') or jobs[job],
                              'A': (a.get('proposal') or {}).get('cover_letter', ''),
                              'B': (b.get('proposal') or {}).get('cover_letter', ''),
                              'A_answers': (a.get('proposal') or {}).get('screening_answers', []),
                              'B_answers': (b.get('proposal') or {}).get('screening_answers', []),
                              'evidence': list({e['evidence_id']: e for r in [a, b] for e in r.get('evidence', [])}.values())})
                pair_key[eid] = {**dict(zip(['A', 'B'], variants, strict=True)), 'persona': persona, 'job_id': job}
        if len(pairs) == 15:
            panel = {'kind': 'panel', 'instructions': 'As a classmate, compare A and B without seeing the pipeline names. Choose A, B, tie or both_poor. Empty text means no usable proposal was produced.', 'items': pairs}
            if (OUT / 'panel.json').exists() and json.loads((OUT / 'panel.json').read_text()) != panel:
                raise ValueError('Panel pack is frozen; do not replace it after collecting votes')
            (OUT / 'panel.json').write_text(json.dumps(panel, indent=2))
            (key / 'panel_key.json').write_text(json.dumps(pair_key, indent=2))
            print('15 anonymous paired panel items ready')
        else:
            print('Panel pending: need five matched bid cases for each persona')
    return pack


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', type=Path, default=Path('evals/results/b4'),
                        help='Evaluation output directory used to build the blind pairwise pack')
    args = parser.parse_args()
    results_dir = args.results_dir if args.results_dir.is_absolute() else ROOT / args.results_dir
    make_packs(results_dir)
