"""Compliance Guard. Rules are config (agent/config.yaml), so a platform-policy change is a YAML edit."""
from __future__ import annotations

import re

from agent.deps import Deps
from agent.handoffs import ComplianceVerdict, ProposalDraft, Violation
from rag.verify import configured_verdicts, normalize_draft, verify_edited_claims

_SENT = re.compile(r"(?<=[.!?])\s+")


def apply_rules(text: str, rules: list[dict]) -> tuple[str, list[Violation]]:
    found: list[Violation] = []
    for r in rules:
        pat = re.compile(r["pattern"])
        for m in pat.finditer(text):
            found.append(Violation(rule=r["id"], match=m.group(0), action=r["action"]))
        if r["action"] == "scrub":
            text = pat.sub("", text)
        elif r["action"] == "drop_sentence":
            text = " ".join(s for s in _SENT.split(text) if not pat.search(s))
    return text.strip(), found


def check_draft(draft: ProposalDraft, rules: list[dict], evidence: list[dict] | None = None) -> tuple[ProposalDraft, ComplianceVerdict]:
    violations: list[Violation] = []
    claims = []
    for c in draft.claims:
        clean, v = apply_rules(c.text, rules)
        violations += v
        if clean:
            claims.append(c.model_copy(update={"text": clean}))
    edited = draft.edited_cover_letter
    if edited is not None:
        edited, v = apply_rules(edited, rules)
        violations += v
    new = draft.model_copy(update={"claims": claims, "edited_cover_letter": edited})
    if not new.cover_letter.strip():
        violations.append(Violation(rule="empty_cover_letter", match="", action="block"))
    if edited is not None and evidence is not None:
        verdicts = verify_edited_claims(edited, new.claims, evidence)
        violations += [Violation(rule="unsupported_edited_claim", match=v.text, action="block")
                       for v in verdicts if v.label != "supported"]
    blocking = sorted({f"{v.rule}: {v.match!r}" for v in violations if v.action == "block"})
    return new, ComplianceVerdict(passed=not blocking, violations=violations, blocking_reasons=blocking)


def make(deps: Deps):
    async def compliance(state):
        draft = ProposalDraft.model_validate(state["proposal_draft"])
        evidence = state.get("evidence", [])
        new, verdict = check_draft(draft, deps.cfg["compliance"]["rules"], evidence)
        out = {"proposal_draft": new, "compliance_verdict": verdict}
        if new.edited_cover_letter is not None:
            normalized = normalize_draft(new, evidence)
            checked = await configured_verdicts(normalized.claims, evidence, deps.llm, deps.cfg['verification'])
            out['claim_verification'] = checked
            bad = [Violation(rule='unsupported_edited_claim', match=v.text, action='block')
                   for v in checked if v.label != 'supported']
            if bad:
                verdict = verdict.model_copy(update={'passed': False, 'violations': verdict.violations + bad,
                    'blocking_reasons': sorted(set(verdict.blocking_reasons + [f'unsupported_edited_claim: {v.text!r}' for v in checked if v.label != 'supported']))})
                out['compliance_verdict'] = verdict
        return out
    return compliance
