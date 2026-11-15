from __future__ import annotations

from agent.deps import Deps
from agent.handoffs import ProposalDraft
from rag.verify import apply_verification, configured_verdicts, normalize_draft


def make(deps: Deps):
    v = deps.cfg["verification"]

    async def verifier(state):
        draft = normalize_draft(ProposalDraft.model_validate(state["proposal_draft"]), state['evidence'])
        verdicts = await configured_verdicts(draft.claims, state['evidence'], deps.llm, v)
        clean, stats = apply_verification(draft, verdicts)
        if deps.cfg['defences']['verify_claims'] and clean.claims:
            post = await configured_verdicts(clean.claims, state['evidence'], deps.llm, v)
            clean, post_stats = apply_verification(clean, post)
            stats.update({'claims_after': len(clean.claims), 'removed_claims': len(draft.claims) - len(clean.claims),
                          'unsupported_on_recheck': post_stats['unsupported_before'],
                          'partly_supported_on_recheck': post_stats['partly_supported_before'],
                          'unsupported_after': post_stats['unsupported_after'],
                          'partly_supported_after': post_stats['partly_supported_after'],
                          'unsupported_rate_after': post_stats['unsupported_rate_after'],
                          'removed_texts': stats['removed_texts'] + post_stats['removed_texts'],
                          'recheck_verdicts': [x.model_dump() for x in post]})
        if not deps.cfg["defences"]["verify_claims"]:          # eval-only switch: nothing is removed
            clean, stats = draft, {**stats, "unsupported_after": stats["unsupported_before"],
                                  "partly_supported_after": stats["partly_supported_before"],
                                  'claims_after': len(draft.claims), 'removed_claims': 0, 'removed_texts': [],
                                  'unsupported_rate_after': stats['unsupported_rate_before']}
        return {"proposal_draft": clean,
                "claim_verification": verdicts,
                "verification_stats": stats}
    return verifier
