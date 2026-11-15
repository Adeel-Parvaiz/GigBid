"""Client Liaison nodes (conversation graph). Client messages are untrusted data, like job posts."""
from __future__ import annotations

import difflib
import hashlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from langgraph.types import interrupt

from agent.deps import Deps
from agent.handoffs import (
    ApprovalDecision,
    Claim,
    ClaimVerdict,
    ComplianceVerdict,
    IntentResult,
    ReplyDraft,
    Violation,
)
from agent.marketplace_context import approved_write
from agent.marketplace_port import MarketplaceError
from agent.nodes.compliance import apply_rules
from rag.retriever import RetrievalQuery
from rag.verify import split_claims, verify_claims, verify_edited_claims


def calendar_start_date(config: dict, now: datetime | None = None) -> str:
    value = config.get("start_date", "today")
    if value != "today":
        return value
    zone = ZoneInfo(config.get("timezone", "Asia/Karachi"))
    return (now.astimezone(zone) if now else datetime.now(zone)).date().isoformat()


def last_client_message(thread: dict) -> str:
    return next((m["text"] for m in reversed(thread["messages"]) if m["from"] == "client"), "")


def make_load(deps: Deps):
    async def load_thread(state):
        try:
            thread = await deps.port.list_messages(state["thread_id"])
            return {"thread": thread, "job_id": thread.get("job_id", state["thread_id"])}
        except MarketplaceError as e:
            if e.code == "rate_limited":
                raise
            return {"status": "error", "errors": [str(e)]}
    return load_thread


def make_classify(deps: Deps):
    async def classify(state):
        msg = last_client_message(state["thread"])
        llm = await deps.llm.structured("liaison_intent", IntentResult, {"message": msg})
        flags = set(llm.flags)
        if re.search(deps.cfg["conversation"]["scam_patterns"], msg):
            flags.add("scam_pattern")
        if re.search(deps.cfg["risk"]["patterns"]["prompt_injection"], msg, flags=re.M):
            flags.add("prompt_injection")
        intent = "scam_signal" if flags else llm.intent          # rule floor: the LLM cannot talk its way out
        if not flags and re.search(deps.cfg["conversation"]["interview_patterns"], msg):
            intent = "interview_request"
        return {"intent": IntentResult(intent=intent, rationale=llm.rationale, flags=sorted(flags)),
                "status": "flagged" if flags else ""}
    return classify


def make_slots(deps: Deps):
    async def propose_slots(state):
        intent = IntentResult.model_validate(state["intent"])
        if intent.intent != "interview_request":
            return {"slots": []}
        c = deps.cfg["conversation"]["slots"]
        res = await deps.workspace.get_free_slots(calendar_start_date(deps.cfg["conversation"]), c["days"],
                                                  c["duration_minutes"], c["offer"])
        return {"slots": [s.start for s in res.slots]}
    return propose_slots


def make_reply(deps: Deps):
    async def draft_reply(state):
        msg, fid = last_client_message(state["thread"]), state["profile"]["freelancer_id"]
        intent = IntentResult.model_validate(state["intent"])
        ev = []
        if intent.intent == "question":
            ev = await deps.retriever.retrieve(RetrievalQuery(msg, [], {"freelancer_id": fid}), 3)
        draft = await deps.llm.structured("liaison_reply", ReplyDraft, {
            "thread_id": state["thread_id"], "intent": intent.intent, "message": msg,
            "evidence": ev, "slots": state.get("slots", [])})
        # slots are NEVER model-authored: drop any logistics claim the model wrote, append ours from tool data
        draft = draft.model_copy(update={"thread_id": state["thread_id"], "offered_slots": list(state.get("slots", [])),
                                         "claims": [c for c in draft.claims if c.kind != "logistics"]})
        slots = state.get("slots", [])
        if slots:
            draft = draft.model_copy(update={"offered_slots": slots, "claims": draft.claims + [
                Claim(text="I could meet at " + ", ".join(slots) + ".", kind="logistics")]})
        draft = draft.model_copy(update={'claims': split_claims(draft.claims)})
        verdicts = verify_claims(draft.claims, ev)                # no unsupported experience claims in replies either
        keep = [c for c, v in zip(draft.claims, verdicts, strict=True) if v.label == "supported"]
        draft = draft.model_copy(update={"claims": keep})
        return {"reply": draft, "evidence": ev, "claim_verification": verdicts}
    return draft_reply


def make_compliance(deps: Deps):
    async def compliance(state):
        rules, d = deps.cfg["compliance"]["rules"], ReplyDraft.model_validate(state["reply"])
        viol, claims = [], []
        for c in d.claims:
            clean, v = apply_rules(c.text, rules)
            viol += v
            if clean:
                claims.append(c.model_copy(update={"text": clean}))
        edited = d.edited_text
        if edited is not None:
            edited, v = apply_rules(edited, rules)
            viol += v
            verdicts = verify_edited_claims(edited, d.claims, state.get("evidence", []))
            viol += [Violation(rule="unsupported_edited_claim", match=v.text, action="block")
                     for v in verdicts if v.label != "supported"]
        if not (edited if edited is not None else " ".join(c.text for c in claims)).strip():
            viol.append(Violation(rule="empty_reply", match="", action="block"))
        blocking = sorted({f"{v.rule}: {v.match!r}" for v in viol if v.action == "block"})
        d = d.model_copy(update={"claims": claims, "edited_text": edited})
        out = {"reply": d,
               "compliance_verdict": ComplianceVerdict(passed=not blocking, violations=viol, blocking_reasons=blocking)}
        if edited is not None:
            out["claim_verification"] = verdicts
        return out
    return compliance


def make_approval(deps: Deps):
    async def approval(state):
        d = ReplyDraft.model_validate(state["reply"])
        compliance = ComplianceVerdict.model_validate(state["compliance_verdict"])
        intent = IntentResult.model_validate(state["intent"])
        blocking = list(compliance.blocking_reasons)
        payload = {"kind": "message_approval", "thread_id": state["thread_id"],
                   "intent": intent.model_dump(mode="json"),
                   "client_message": last_client_message(state["thread"]), "draft": d.model_dump(mode="json"),
                   "evidence": state.get("evidence", []), "offered_slots": d.offered_slots,
                   "claim_verification": [
                       ClaimVerdict.model_validate(v).model_dump(mode="json")
                       for v in state.get("claim_verification", [])
                   ],
                   "compliance_verdict": compliance.model_dump(mode="json"), "blocking_reasons": blocking,
                   "allowed_actions": ["edit", "reject"] if blocking else ["approve", "edit", "reject"]}
        edits = state.get("edit_history") or []
        if edits:
            payload["edit_diff"] = edits[-1]["diff"]
        while True:
            decision = ApprovalDecision.model_validate(interrupt(payload))
            if decision.action == "approve" and blocking:
                payload = {**payload, "error": "cannot approve while blocked", "allowed_actions": ["edit", "reject"]}
                continue
            break
        if decision.action == "edit":
            edited = decision.edited_cover_letter
            if edited is None:
                raise ValueError("an edit must include non-empty edited text")
            diff = "\n".join(difflib.unified_diff(d.text.splitlines(), edited.splitlines(), lineterm=""))
            new = d.model_copy(update={"edited_text": edited})
            return {"approval": decision, "reply": new, "edit_history": [
                {"job_id": state["job_id"], "diff": diff, "original": d.text, "edited": edited}
            ]}
        return {"approval": decision, "status": "rejected" if decision.action == "reject" else ""}
    return approval


def make_send(deps: Deps):
    async def send_reply(state):
        d = ReplyDraft.model_validate(state["reply"])
        key = hashlib.sha256(f"{state['profile']['freelancer_id']}|{state['thread_id']}|{d.text}".encode()).hexdigest()[:32]
        approval = state.get("approval")
        approval_token = approved_write.set(
            approval is not None and ApprovalDecision.model_validate(approval).action == "approve"
        )
        try:
            sent = await deps.port.send_message(state["thread_id"], d.text, key)
            hold = None
            if d.offered_slots:       # tentative hold for the first offered slot, only after the human approved
                h = await deps.workspace.create_tentative_hold(
                    d.offered_slots[0], f"Interview ({state['thread']['job_id']})",
                    hashlib.sha256(f"{state['thread_id']}|{d.offered_slots[0]}".encode()).hexdigest()[:32])
                hold = h.model_dump()
        except (MarketplaceError, ValueError) as e:
            return {"status": "needs_attention", "errors": [str(e)]}
        finally:
            approved_write.reset(approval_token)
        return {"send_result": {**sent, "hold": hold}, "status": 'awaiting_platform_confirmation' if sent.get('status') == 'awaiting_platform_confirmation' else 'sent'}
    return send_reply


_ = Claim  # re-exported for type checkers
