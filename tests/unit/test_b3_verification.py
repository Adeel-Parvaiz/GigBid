import pytest

from agent.handoffs import Claim, ProposalDraft
from rag.verify import (
    SemanticBatch,
    SemanticDecision,
    apply_verification,
    normalize_draft,
    verify_claims,
    verify_semantic,
)

EV = [{'evidence_id': 'e1', 'title': 'Classification study', 'skills': ['Python'],
       'summary': 'Built a Python classification baseline in 2019. Compared logistic regression and random forest.', 'outcome': ''}]


def test_compound_and_mislabelled_claims_cannot_hide_unsupported_experience():
    draft = ProposalDraft(job_id='j', claims=[Claim(
        text='Built a Python classification baseline in 2019. I deployed Kubernetes for 19 banks.',
        evidence_ids=['e1'], kind='boilerplate')])
    labels = verify_claims(draft.claims, EV)
    assert [v.label for v in labels] == ['supported', 'unsupported']
    clean, stats = apply_verification(draft, labels)
    assert 'Kubernetes' not in clean.cover_letter
    assert stats['claims_total'] == 2 and stats['claims_after'] == 1
    assert stats['unsupported_before'] == 1 and stats['unsupported_after'] == 0


def test_unknown_citations_do_not_fall_back_and_numbers_match_whole_values():
    for claim in [Claim(text='Built a Python classification baseline.', evidence_ids=['fake']),
                  Claim(text='Built a Python classification baseline in 19.', evidence_ids=['e1']),
                  Claim(text='Built a Python classification baseline.', evidence_ids=[])]:
        assert verify_claims([claim], EV)[0].label == 'unsupported'


def test_edited_cover_is_split_and_cannot_override_filtered_claims():
    draft = normalize_draft(ProposalDraft(job_id='j', edited_cover_letter='Hello. I have 99 years of experience.'), EV)
    clean, stats = apply_verification(draft, verify_claims(draft.claims, EV))
    assert clean.edited_cover_letter is None and clean.cover_letter == 'Hello.'
    assert stats['unsupported_before'] == 1
    verdicts = verify_claims([Claim(text='Hi.', kind='boilerplate')], EV)
    with pytest.raises(ValueError, match='do not match'):
        apply_verification(ProposalDraft(job_id='j', claims=[Claim(text='Other text.')]), verdicts)


async def test_semantic_support_requires_exact_cited_quote_and_complete_index():
    class Model:
        async def structured(self, node, schema, inputs):
            assert node == 'claim_verifier'
            definitions = schema.model_json_schema()['$defs']
            assert {'evidence_id', 'quote'} <= set(definitions['CitedClaimDecision']['required'])
            return SemanticBatch(decisions=[SemanticDecision(index=0, label='supported', evidence_id='e1',
                quote='Compared logistic regression and random forest.', reason='The source states the comparison.'),
                SemanticDecision(index=1, label='supported', evidence_id='e1', quote='invented passage', reason='Bad quote')])
    claims = [Claim(text='I compared two classification algorithms.', evidence_ids=['e1']),
              Claim(text='I deployed a global service.', evidence_ids=['e1']),
              Claim(text='I ran model evaluation.', evidence_ids=['e1'])]
    result = await verify_semantic(claims, EV, Model())
    assert [v.label for v in result] == ['supported', 'unsupported', 'unsupported']


async def test_semantic_partial_and_failure_are_never_promoted_to_supported():
    class Partial:
        async def structured(self, node, schema, inputs):
            return SemanticBatch(decisions=[SemanticDecision(index=0, label='partly_supported', evidence_id='e1',
                quote='Built a Python classification baseline in 2019.', reason='No deployment is stated.')])
    claim = Claim(text='I built a Python baseline and deployed it globally.', evidence_ids=['e1'])
    verdicts = await verify_semantic([claim], EV, Partial())
    assert verdicts[0].label == 'partly_supported'
    clean, _ = apply_verification(ProposalDraft(job_id='j', claims=[claim]), verdicts)
    assert not clean.claims
    class Offline:
        async def structured(self, *args):
            raise ConnectionError('fixture unavailable')
    with pytest.raises(ConnectionError):
        await verify_semantic([Claim(text='I compared two classification algorithms.', evidence_ids=['e1'])], EV, Offline())
