from fastapi import APIRouter, Depends, HTTPException, Request

from agent.handoffs import ApprovalDecision, Claim, ParagraphRewrite, ProposalDraft
from agent.nodes.compliance import apply_rules
from agent.token_budget import TokenBudget, current_token_budget
from apps.api.deps import get_run, get_user
from apps.api.dispatch import resume_run
from apps.api.routers.jobs import _run_out
from apps.api.schemas import ParagraphRegenerationIn, ParagraphRegenerationOut, RunOut
from rag.verify import configured_verdicts, split_claims

router = APIRouter(tags=["approvals"])


@router.post("/runs/{run_id}/regenerate-paragraph", response_model=ParagraphRegenerationOut)
async def regenerate_paragraph(
    body: ParagraphRegenerationIn,
    request: Request,
    run: dict = Depends(get_run),
):
    if run["kind"] != "bid" or run["status"] != "awaiting_approval":
        raise HTTPException(409, "paragraph regeneration is only available for a pending proposal")
    manager = request.app.state.manager
    pending = await manager.pending(run)
    if not pending or pending.get("kind") != "proposal_approval":
        raise HTTPException(409, "no proposal is waiting for approval")
    values = await manager.values(run)
    draft = ProposalDraft.model_validate(values["proposal_draft"])
    cover_claims = [claim for claim in draft.claims if claim.section == "cover"]
    if body.claim_index >= len(cover_claims):
        raise HTTPException(422, "paragraph index is outside the current proposal")
    selected = cover_claims[body.claim_index]
    if selected.kind != "claim" or not selected.evidence_ids:
        raise HTTPException(422, "only an evidence-backed paragraph can be regenerated")
    evidence_by_id = {item["evidence_id"]: item for item in values.get("evidence", [])}
    if any(evidence_id not in evidence_by_id for evidence_id in selected.evidence_ids):
        raise HTTPException(409, "proposal evidence is no longer available")
    evidence = [evidence_by_id[evidence_id] for evidence_id in selected.evidence_ids]
    config = manager.deps.cfg
    budget = TokenBudget(config["budgets"]["max_tokens_per_job"], int(values.get("tokens_used") or 0),
                         "paragraph_rewriter")
    token = current_token_budget.set(budget)
    try:
        rewritten = await manager.deps.llm.structured("paragraph_rewriter", ParagraphRewrite, {
            "job": values["job"], "job_spec": values["job_spec"], "original_paragraph": selected.text,
            "evidence": evidence,
        })
        if not rewritten.text.strip() or "\n" in rewritten.text:
            raise HTTPException(502, "model returned an invalid paragraph")
        allowed_ids = set(selected.evidence_ids)
        if not rewritten.evidence_ids or not set(rewritten.evidence_ids) <= allowed_ids:
            raise HTTPException(502, "model returned evidence references outside this paragraph")
        claim = Claim(text=rewritten.text.strip(), evidence_ids=rewritten.evidence_ids, kind="claim", section="cover")
        rewritten_claims = split_claims([claim])
        verdicts = await configured_verdicts(rewritten_claims, evidence, manager.deps.llm, config["verification"])
        unsupported = [verdict for verdict in verdicts if verdict.label != "supported"]
        if not verdicts or unsupported:
            reasons = "; ".join(f"{verdict.label}: {verdict.reason}" for verdict in unsupported)
            raise HTTPException(422, "regenerated paragraph did not pass evidence verification" + (f": {reasons}" if reasons else ""))
        clean, violations = apply_rules(rewritten.text.strip(), config["compliance"]["rules"])
        if clean != rewritten.text.strip() or violations:
            raise HTTPException(422, "regenerated paragraph did not pass compliance")
        if budget.total_used > budget.limit:
            raise HTTPException(409, "token budget exceeded; review this run before continuing")
        return ParagraphRegenerationOut(text=clean)
    finally:
        current_token_budget.reset(token)
        if budget.usage:
            manager.store.record_extra_usage(run["run_id"], budget.usage)


@router.get("/approvals/pending")
async def pending(request: Request, user: dict = Depends(get_user)):
    """What a page refresh calls. Read from the checkpoint, so it survives refreshes and API restarts."""
    m, out = request.app.state.manager, []
    for r in m.store.list(user["user_id"]):
        if r["status"] == "awaiting_approval":
            out.append({"run": _run_out(r), "payload": await m.pending(r)})
    return out


@router.post("/runs/{run_id}/approval", response_model=RunOut, status_code=202)
async def decide(body: ApprovalDecision, request: Request, run: dict = Depends(get_run)):
    if run["status"] == "superseded":
        raise HTTPException(409, "run was superseded; review the current run instead")
    m = request.app.state.manager
    payload = await m.pending(run)
    if payload is None:
        raise HTTPException(409, "run has no pending approval")
    if body.action not in payload["allowed_actions"]:
        raise HTTPException(409, f"action {body.action!r} not allowed here: {payload.get('blocking_reasons')}")
    if run["status"] != "awaiting_approval":
        raise HTTPException(409, "this approval has already been queued or completed")
    return _run_out(await resume_run(request, run, body.model_dump()))
