"""Human-rating validation and calibration. No model/database dependencies."""
from __future__ import annotations

import hashlib
import json
from collections import Counter


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_rating(payload, pack):
    expected = {item['id'] for item in pack['items']}
    if payload.get('pack_sha256') != digest(pack):
        raise ValueError('Ratings belong to a different review pack')
    if payload.get('personally_reviewed') is not True:
        raise ValueError('A real reviewer must confirm personally reviewing every item')
    alias = payload.get('reviewer', '').strip()
    if not 2 <= len(alias) <= 80:
        raise ValueError('Provide a reviewer alias of 2–80 characters')
    labels = payload.get('labels', [])
    if not isinstance(labels, list) or len(labels) != len(expected):
        raise ValueError('Every item needs exactly one rating')
    if {r.get('id') for r in labels} != expected:
        raise ValueError('Missing, repeated or unknown review item')
    if pack['kind'] == 'calibration':
        if len(labels) < 30:
            raise ValueError('Calibration requires at least 30 personally labelled items')
        if any(type(r.get('score')) is not int or not 0 <= r['score'] <= 4 for r in labels):
            raise ValueError('Each overall quality score must be an integer from 0 to 4')
        if payload.get('role') != 'author':
            raise ValueError('Calibration must be labelled by the assignment author')
    else:
        if payload.get('role') != 'classmate':
            raise ValueError('Panel votes must come from classmates')
        if any(r.get('choice') not in {'A', 'B', 'tie', 'both_poor'} for r in labels):
            raise ValueError('Choose A, B, tie or both_poor for every pair')
    return {**payload, 'reviewer': alias}


def kappa(human, judge):
    if len(human) < 30 or len(human) != len(judge):
        raise ValueError('Kappa requires at least 30 aligned labels')
    n = len(human)
    observed = sum(a == b for a, b in zip(human, judge, strict=True)) / n
    a, b = Counter(human), Counter(judge)
    expected = sum(a[c] * b[c] for c in a.keys() | b.keys()) / n**2
    return {'n': n, 'agreement': observed, 'kappa': (observed - expected) / (1 - expected) if expected < 1 else None,
            'note': 'Unweighted Cohen kappa; constant identical labels have undefined kappa.'}


def calibration(pack, human, predictions):
    human = validate_rating(human, pack)
    if len(predictions) != len(pack['items']) or len({r['id'] for r in predictions}) != len(predictions):
        raise ValueError('Exactly one judge prediction is required per item')
    if any(type(r.get('overall')) is not int or not 0 <= r['overall'] <= 4 for r in predictions):
        raise ValueError('Judge labels must use the same integer 0–4 rubric')
    predicted = {r['id']: r['overall'] for r in predictions}
    if set(predicted) != {r['id'] for r in pack['items']}:
        raise ValueError('Judge predictions must cover the same complete calibration pack')
    ordered = sorted(human['labels'], key=lambda r: r['id'])
    result = kappa([r['score'] for r in ordered], [predicted[r['id']] for r in ordered])
    return {**result, 'status': 'calibration_measured', 'pack_sha256': digest(pack),
            'disagreements': [r['id'] for r in ordered if r['score'] != predicted[r['id']]],
            'human_source': 'personally labelled author ratings; self-attested'}


def panel_summary(pack, reviews, key):
    accepted = [validate_rating(r, pack) for r in reviews]
    if len({r['reviewer'].casefold() for r in accepted}) != len(accepted):
        raise ValueError('A reviewer cannot count twice in the panel')
    scores, by_persona = Counter(), {}
    for review in accepted:
        for label in review['labels']:
            choice = label['choice']
            winner = key[label['id']][choice] if choice in {'A', 'B'} else choice
            scores[winner] += 1
            persona = key[label['id']].get('persona', 'unspecified')
            by_persona.setdefault(persona, Counter())[winner] += 1
    return {'status': 'collected' if len(accepted) >= 2 else 'pending_classmates',
            'raters': len(accepted), 'votes': dict(scores), 'per_persona': by_persona, 'pairs_per_rater': len(pack['items']),
            'note': 'Blind side allocation; self-attested classmates. No generated or inferred human votes.'}
