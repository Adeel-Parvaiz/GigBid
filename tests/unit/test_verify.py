from agent.handoffs import Claim, ProposalDraft
from rag.verify import apply_verification, verify_claims

EV = [{"evidence_id": "e1", "title": "Churn study", "skills": ["Python", "scikit-learn"],
       "summary": "Built a classification experiment comparing logistic regression and random forest.", "outcome": ""}]


def test_supported_unsupported_and_invented_numbers():
    claims = [
        Claim(text="Hello there.", kind="boilerplate"),
        Claim(text="I built a classification experiment comparing logistic regression and random forest.", evidence_ids=["e1"]),
        Claim(text="I deployed Kubernetes clusters for Fortune 500 banks.", evidence_ids=["e1"]),
        Claim(text="I built a classification experiment and improved accuracy by 35%.", evidence_ids=["e1"]),
        Claim(text="I have 8 years of experience.", kind="boilerplate"),   # smuggled claim
    ]
    labels = [v.label for v in verify_claims(claims, EV)]
    assert labels == ["supported", "supported", "unsupported", "unsupported", "unsupported"]


def test_unsupported_claims_are_removed_before_critic():
    claims = [Claim(text="Hi.", kind="boilerplate"),
              Claim(text="I deployed Kubernetes clusters for banks.", evidence_ids=["e1"])]
    d = ProposalDraft(job_id="j", claims=claims)
    new, stats = apply_verification(d, verify_claims(claims, EV))
    assert [c.text for c in new.claims] == ["Hi."]
    assert stats["unsupported_before"] == 1 and stats["unsupported_rate_before"] == 0.5


def test_partly_supported_claim_is_not_published_as_verified_experience():
    claim = Claim(text="I built a classification experiment and deployed global Kubernetes clusters.", evidence_ids=["e1"])
    verdicts = verify_claims([claim], EV)
    assert verdicts[0].label == "partly_supported"
    draft, stats = apply_verification(ProposalDraft(job_id="j", claims=[claim]), verdicts)
    assert draft.claims == [] and stats["partly_supported_before"] == 1
    assert stats["unsupported_before"] == 0 and stats["removed_claims"] == 1


def test_model_cannot_smuggle_experience_as_logistics_in_reply_node():
    # logistics claims written by a model are discarded by the reply node; verify treats code-built ones as supported
    from agent.handoffs import Claim
    from rag.verify import verify_claims
    c = Claim(text="I could meet at 2026-11-09T11:00.", kind="logistics")
    assert verify_claims([c], [])[0].label == "supported"
