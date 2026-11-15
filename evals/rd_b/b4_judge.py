"""Generate provisional local-model rubric predictions; never generate human labels."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from evals.rd_b.review_data import digest

ROOT = Path(__file__).resolve().parents[2]
DIMENSIONS = ('grounding', 'fit', 'plan', 'answers', 'professionalism')


def predict(item, endpoint, model):
    if urlparse(endpoint).hostname not in {'127.0.0.1', 'localhost'}:
        raise ValueError('Only the already authorized local inference endpoint is supported')
    properties = {name: {'type': 'integer', 'minimum': 0, 'maximum': 4} for name in [*DIMENSIONS, 'overall']}
    properties['reason'] = {'type': 'string'}
    schema = {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}
    body = {'model': model, 'temperature': 0, 'seed': 4016, 'max_tokens': 600,
            'response_format': {'type': 'json_schema', 'json_schema': {'name': 'ProposalRubric', 'schema': schema}},
            'messages': [{'role': 'system', 'content': (ROOT / 'agent/prompts/proposal_judge.md').read_text()},
                         {'role': 'user', 'content': '<data>' + json.dumps(item) + '</data>'}]}
    start = time.perf_counter()
    with urlopen(Request(endpoint.rstrip('/') + '/chat/completions', data=json.dumps(body).encode(),
                         headers={'Content-Type': 'application/json'}), timeout=180) as response:
        raw = json.load(response)
    result = json.loads(raw['choices'][0]['message']['content'])
    if any(type(result.get(k)) is not int or not 0 <= result[k] <= 4 for k in [*DIMENSIONS, 'overall']):
        raise ValueError('Judge returned an invalid rubric score')
    return {'id': item['id'], **result, 'usage': raw.get('usage'), 'seconds': time.perf_counter() - start,
            'model': raw.get('model', model), 'raw_response': raw['choices'][0]['message']['content'],
            'status': 'provisional_until_author_calibration'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://127.0.0.1:11435/v1')
    parser.add_argument('--model', default='qwen25-15b')
    parser.add_argument('--target', choices=['calibration', 'proposals'], default='calibration')
    parser.add_argument('--results-dir', type=Path, default=Path('evals/results/b4'),
                        help='Evaluation output directory')
    args = parser.parse_args()
    folder = args.results_dir if args.results_dir.is_absolute() else ROOT / args.results_dir
    if args.target == 'calibration':
        pack = json.loads((ROOT / 'evals/reviews/b4/calibration.json').read_text())
    else:
        rows = [json.loads(line) for line in (folder / 'runs.jsonl').read_text().splitlines()]
        pack = {'kind': 'proposals', 'items': [{'id': digest([r['persona'], r['job_id'], r['variant']]),
            'job': r.get('job'), 'proposal': (r.get('proposal') or {}).get('cover_letter', ''),
            'screening_answers': (r.get('proposal') or {}).get('screening_answers', []),
            'evidence': r.get('evidence', [])} for r in rows if r.get('proposal') is not None]}
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ('judge_calibration_predictions.jsonl' if args.target == 'calibration' else 'judge_proposal_predictions.jsonl')
    previous = [json.loads(line) for line in target.read_text().splitlines()] if target.exists() else []
    done = {r['id'] for r in previous}
    for item in pack['items']:
        if item['id'] in done:
            continue
        result = predict(item, args.endpoint, args.model)
        result['item_sha256'] = digest(item)
        if args.target == 'calibration':
            result['pack_sha256'] = digest(pack)
        with target.open('a') as output:
            output.write(json.dumps(result) + '\n')
        print('Provisional judge', len(done) + 1, '/', len(pack['items']), flush=True)
        done.add(item['id'])


if __name__ == '__main__':
    main()
