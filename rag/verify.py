"""B3: sentence-level verification, deterministic guards and optional semantic checks."""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

from agent.handoffs import Claim, ClaimVerdict, ProposalDraft

STOP = set(["a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "from", "by", "at", "as", "is", "are", "was", "were", "be", "been", "i", "my", "me", "we", "our", "you", "your", "this", "that", "these", "those", "it", "its", "into", "over", "under", "about", "using", "used", "use", "also", "very", "more", "most", "such", "than", "then", "so", "if", "not", "no", "can", "could", "would", "should", "will", "just", "have", "has", "had", "do", "did", "does"])
EXPERIENCE_WORDS = re.compile(r"(?i)\b(experience|expert|certified|years?|clients?|senior|lead|led|managed)\b")
PAST_WORK = re.compile(r"(?i)\b(built|developed|delivered|deployed|designed|implemented|created|worked|improved|increased|reduced|achieved|trained|integrated|migrated|automated|scaled|optimized|launched|shipped|secured|contributed)\b")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+|;\s+', text.strip()) if s.strip()]


def factual(claim: Claim) -> bool:
    return claim.kind == 'claim' or bool(re.search(r'\d', claim.text) or EXPERIENCE_WORDS.search(claim.text)
        or PAST_WORK.search(claim.text) or re.search(r'(?i)\bI (?:have|know|am proficient|am skilled)\b', claim.text))


def split_claims(claims: list[Claim]) -> list[Claim]:
    return [c.model_copy(update={'text': sentence}) for c in claims for sentence in sentences(c.text)]


def normalize_draft(draft: ProposalDraft, evidence: list[dict]) -> ProposalDraft:
    claims = split_claims(draft.claims)
    if draft.edited_cover_letter is not None:
        known = {c.text: c for c in claims if c.section == 'cover'}
        claims = [c for c in claims if c.section != 'cover'] + [known.get(text) or Claim(
            text=text, kind='boilerplate', evidence_ids=[e['evidence_id'] for e in evidence])
            for text in sentences(draft.edited_cover_letter)]
    return draft.model_copy(update={'claims': claims, 'edited_cover_letter': None})


def verify_edited_claims(text: str, originals: list[Claim], evidence: list[dict],
                         supported_at: float = .70, partly_at: float = .35) -> list[ClaimVerdict]:
    known = {c.text.strip(): c for c in originals}
    claims = []
    for sentence in sentences(text):
        if not sentence.strip():
            continue
        if sentence in known:
            claims.append(known[sentence])
        else:
            claims.append(Claim(text=sentence, kind='boilerplate', evidence_ids=[e['evidence_id'] for e in evidence]))
    return verify_claims(claims, evidence, supported_at, partly_at)


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9+#.\-]*", text.lower())
    return {_stem(w.strip(".-")) for w in words if w.strip(".-") not in STOP}


def _evidence_text(ev: dict[str, Any]) -> str:
    return f"{ev.get('title', '')} {ev.get('summary', '')} {' '.join(ev.get('skills', []))} {ev.get('outcome', '')}"


def verify_claims(claims: list[Claim], evidence: list[dict[str, Any]],
                  supported_at: float = 0.70, partly_at: float = 0.35) -> list[ClaimVerdict]:
    by_id = {e["evidence_id"]: e for e in evidence}
    verdicts: list[ClaimVerdict] = []
    for c in split_claims(claims):
        is_claim = factual(c)
        if c.kind == "logistics":
            verdicts.append(ClaimVerdict(text=c.text, section=c.section, label="supported", support=1.0,
                                         reason="built by code from calendar tool output"))
            continue
        if not is_claim:
            verdicts.append(ClaimVerdict(text=c.text, section=c.section, label="supported", support=1.0,
                                         reason="boilerplate, no experience claimed"))
            continue
        if not c.evidence_ids or any(i not in by_id for i in c.evidence_ids):
            verdicts.append(ClaimVerdict(text=c.text, section=c.section, label='unsupported', support=0,
                reason='guard: missing or unknown evidence citation'))
            continue
        pool = [by_id[i] for i in c.evidence_ids]
        # One source must support the claim; don't combine unrelated fragments into apparent proof.
        ctoks = _tokens(c.text)
        best = max(pool, key=lambda e: len(ctoks & _tokens(_evidence_text(e))))
        ev_text = _evidence_text(best)
        ctoks, etoks = _tokens(c.text), _tokens(ev_text)
        missing_numbers = [n for n in re.findall(r"\d+(?:\.\d+)?%?", c.text)
                           if n not in re.findall(r"\d+(?:\.\d+)?%?", ev_text)]
        support = len(ctoks & etoks) / len(ctoks) if ctoks else 0.0
        if missing_numbers:
            verdicts.append(ClaimVerdict(text=c.text, section=c.section, label="unsupported",
                                         support=round(support, 2),
                                         reason=f"guard: numbers not in evidence: {missing_numbers}"))
            continue
        entities = re.findall(r'\b(?:at|for)\s+([A-Z][\w.-]*(?:\s+[A-Z][\w.-]*)*)', c.text)
        if any(entity.lower() not in ev_text.lower() for entity in entities):
            verdicts.append(ClaimVerdict(text=c.text, section=c.section, label='unsupported', support=round(support, 2),
                                         reason='guard: named organization or project is absent from the cited source'))
            continue
        qualifications = re.findall(r'(?i)\b(extensive|expert|senior|certified|leading)\b', c.text)
        if any(q.lower() not in ev_text.lower() for q in qualifications):
            verdicts.append(ClaimVerdict(text=c.text, section=c.section, label='partly_supported' if support >= partly_at else 'unsupported',
                support=round(support, 2), reason='guard: experience level or qualification not established by the source'))
            continue
        label = "supported" if support >= supported_at else "partly_supported" if support >= partly_at else "unsupported"
        new_actions = [m.group(0) for m in PAST_WORK.finditer(c.text)
                       if _stem(m.group(0).lower()) not in _tokens(ev_text)]
        if new_actions and label == 'supported':
            label = 'partly_supported'
        verdicts.append(ClaimVerdict(text=c.text, section=c.section, label=label, support=round(support, 2),
                                     reason=('guard: additional accomplishments absent from the cited source' if new_actions
                                             else 'lexical overlap against one cited source; not semantic proof')))
    return verdicts


def apply_verification(draft: ProposalDraft, verdicts: list[ClaimVerdict]) -> tuple[ProposalDraft, dict]:
    """Drop unsupported claims before the Critic sees the draft. Returns (new draft, stats)."""
    claims = split_claims(draft.claims)
    if any(c.text != v.text or c.section != v.section for c, v in zip(claims, verdicts, strict=True)):
        raise ValueError('Verification verdicts do not match draft claim text/sections')
    kept = [(c, v) for c, v in zip(claims, verdicts, strict=True) if v.label == 'supported']
    keep = [c for c, _ in kept]
    total = len(claims)
    unsupported = sum(v.label == "unsupported" for v in verdicts)
    partly = sum(v.label == "partly_supported" for v in verdicts)
    stats = {"claims_total": total, "unsupported_before": unsupported,
             "unsupported_rate_before": round(unsupported / total, 3) if total else 0.0,
             "partly_supported_before": partly, "removed_claims": total - len(keep),
             'claims_after': len(keep),
             'unsupported_after': sum(v.label == 'unsupported' for _, v in kept),
             'partly_supported_after': sum(v.label == 'partly_supported' for _, v in kept),
             'unsupported_rate_after': sum(v.label == 'unsupported' for _, v in kept) / len(keep) if keep else 0.0,
             'removed_texts': [v.text for v in verdicts if v.label != 'supported']}
    return draft.model_copy(update={"claims": keep, 'edited_cover_letter': None}), stats


class SemanticDecision(BaseModel):
    index: int = Field(ge=0)
    label: str = Field(pattern='^(supported|partly_supported|unsupported)$')
    evidence_id: str = ''
    quote: str = ''
    reason: str


class SemanticBatch(BaseModel):
    decisions: list[SemanticDecision]


async def verify_semantic(claims, evidence, llm, supported_at=.70, partly_at=.35):
    claims = split_claims(claims)
    guards = verify_claims(claims, evidence, supported_at, partly_at)
    pending = [(i, c) for i, c in enumerate(claims) if factual(c) and not guards[i].reason.startswith('guard:')]
    if not pending:
        return guards
    # Constrain small models to actual IDs and verbatim source passages, not ordinal IDs or paraphrased quotes.
    ids = tuple([''] + sorted({e['evidence_id'] for e in evidence}))
    quotes = tuple(dict.fromkeys([''] + [s for e in evidence for s in
        [_evidence_text(e), e.get('summary', ''), *sentences(e.get('summary', ''))] if s]))
    decision_type = create_model('CitedClaimDecision', index=(Literal[tuple(i for i, _ in pending)], ...),
        label=(Literal['supported', 'partly_supported', 'unsupported'], ...), evidence_id=(Literal[ids], ...),
        quote=(Literal[quotes], ...), reason=(str, ...))
    batch_type = create_model('CitedClaimBatch', decisions=(list[decision_type], Field(min_length=len(pending), max_length=len(pending))))
    batch = await llm.structured('claim_verifier', batch_type, {
        'claims': [{'index': i, 'text': c.text, 'evidence_ids': c.evidence_ids} for i, c in pending], 'evidence': evidence})
    by_index = {}
    for decision in batch.decisions:
        by_index.setdefault(decision.index, []).append(decision)
    by_id = {e['evidence_id']: e for e in evidence}
    for index, claim in pending:
        decisions = by_index.get(index, [])
        label, reason, support = 'unsupported', 'semantic check missing, duplicated, or not backed by an exact source quote', 0.0
        if len(decisions) == 1:
            d = decisions[0]
            if d.label == 'unsupported':
                reason = 'semantic: ' + d.reason
            elif d.evidence_id in claim.evidence_ids and d.quote.strip() and d.quote in _evidence_text(by_id[d.evidence_id]):
                label, reason, support = d.label, 'semantic: ' + d.reason, 1.0 if d.label == 'supported' else .5
        guards[index] = ClaimVerdict(text=claim.text, section=claim.section, label=label, support=support, reason=reason)
    return guards


async def configured_verdicts(claims, evidence, llm, config):
    from agent.llm import OpenAICompatLLM
    backend = config.get('backend', 'auto')
    if backend not in {'auto', 'rules', 'llm'}:
        raise ValueError('verification.backend must be auto, rules or llm')
    if backend == 'llm' or (backend == 'auto' and isinstance(llm, OpenAICompatLLM)):
        return await verify_semantic(claims, evidence, llm, config['supported_at'], config['partly_at'])
    return verify_claims(claims, evidence, config['supported_at'], config['partly_at'])
