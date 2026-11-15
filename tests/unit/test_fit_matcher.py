from agent.nodes.fit_matcher import _matches_requirement


def test_requirement_match_accepts_normalized_multiword_skills():
    hit = {
        "title": "Analytics pipeline",
        "summary": "Implemented an end-to-end report.",
        "skills": ["Python", "Data Engineering"],
    }
    assert _matches_requirement("data-engineering", hit)


def test_requirement_match_does_not_promote_weak_overlap():
    hit = {"title": "Python dashboard", "summary": "Built charts.", "skills": ["Python"]}
    assert not _matches_requirement("Python machine learning deployment", hit)
