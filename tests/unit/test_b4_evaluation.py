"""Pure evaluation checks; also runnable without Windows' blocked model DLLs."""
import json
import unittest
from collections import Counter

from evals.rd_b.b4_report import prf, quantile, summarize
from evals.rd_b.b4_run import PROTOCOL, ordered_cases
from evals.rd_b.b4_services import marketplace_env, match_outcome
from evals.rd_b.review_data import calibration, digest, kappa, panel_summary, validate_rating


class EvaluationTests(unittest.TestCase):
    def test_exploratory_sample_is_seeded_and_balanced_per_persona(self):
        protocol = json.loads(PROTOCOL.read_text())
        first = ordered_cases(protocol, per_persona_limit=50)
        second = ordered_cases(protocol, per_persona_limit=50)
        counts = Counter(persona for persona, _ in first)
        self.assertEqual(counts, {persona: 50 for persona in protocol['personas']})
        self.assertEqual(first, second)
        full = ordered_cases(protocol)
        self.assertNotEqual({(p, job['job_id']) for p, job in first},
                            {(p, job['job_id']) for p, job in full[:150]})

    def pack(self):
        return {'kind': 'calibration', 'items': [{'id': str(i)} for i in range(30)]}

    def rating(self):
        return {'reviewer': 'fixture author', 'role': 'author', 'personally_reviewed': True,
                'pack_sha256': digest(self.pack()), 'labels': [{'id': str(i), 'score': i % 5} for i in range(30)]}

    def test_requires_all_personal_labels_and_correct_pack(self):
        validate_rating(self.rating(), self.pack())
        for change in [{'personally_reviewed': False}, {'pack_sha256': 'wrong'}, {'labels': self.rating()['labels'][:-1]}]:
            with self.assertRaises(ValueError):
                validate_rating({**self.rating(), **change}, self.pack())

    def test_kappa_reports_constant_labels_as_undefined(self):
        self.assertIsNone(kappa([0] * 30, [0] * 30)['kappa'])
        result = calibration(self.pack(), self.rating(), [{'id': str(i), 'overall': i % 5} for i in range(30)])
        self.assertEqual(result['kappa'], 1)

    def test_boolean_scores_and_duplicate_ids_are_rejected(self):
        rating = self.rating()
        rating['labels'][0]['score'] = True
        with self.assertRaises(ValueError):
            validate_rating(rating, self.pack())
        rating = self.rating()
        rating['labels'][1]['id'] = '0'
        with self.assertRaises(ValueError):
            validate_rating(rating, self.pack())

    def test_panel_needs_distinct_real_raters(self):
        pack = {'kind': 'panel', 'items': [{'id': 'p'}]}
        review = {'reviewer': 'fixture one', 'role': 'classmate', 'personally_reviewed': True,
                  'pack_sha256': digest(pack), 'labels': [{'id': 'p', 'choice': 'A'}]}
        key = {'p': {'A': 'v0', 'B': 'v8'}}
        self.assertEqual(panel_summary(pack, [review], key)['status'], 'pending_classmates')
        self.assertEqual(panel_summary(pack, [review, {**review, 'reviewer': 'fixture two'}], key)['votes'], {'v0': 2})
        with self.assertRaises(ValueError):
            panel_summary(pack, [review, review], key)

    def test_metrics_do_not_invent_outcomes_or_zero_denominators(self):
        self.assertIsNone(summarize([])['reply_rate_submitted'])
        self.assertEqual(quantile(list(range(1, 101)), .95), 95)
        self.assertEqual(prf([True, False], [True, True])['recall'], .5)

    def test_variant_upstream_accounts_and_outcomes_are_not_mixed(self):
        base = {'MARKETPLACE_AUDIT': 'fixture/audit.jsonl'}
        a = marketplace_env(base, 'v0_naive', 18001)
        b = marketplace_env(base, 'v8_corrective', 18002)
        self.assertNotEqual(a['GIGSIM_API_TOKEN'], b['GIGSIM_API_TOKEN'])
        self.assertNotEqual(a['MARKETPLACE_MCP_TOKENS'], b['MARKETPLACE_MCP_TOKENS'])
        outcomes = [{'draft_id': 'wrong', 'replied': False}, {'draft_id': 'right', 'replied': True}]
        self.assertTrue(match_outcome(outcomes, {'draft_id': 'right'})['replied'])
        with self.assertRaises(ValueError):
            match_outcome(outcomes, {})
        with self.assertRaises(ValueError):
            match_outcome(outcomes, {'draft_id': 'missing'})


if __name__ == '__main__':
    unittest.main()
