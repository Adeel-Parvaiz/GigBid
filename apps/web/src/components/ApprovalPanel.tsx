import { useState } from "react";
import type { Payload } from "../types";
import { EvidenceHover } from "./EvidenceHover";

export interface Decision { action: "approve" | "edit" | "reject"; edited_cover_letter?: string; reason?: string }

/** The human gate: approve, edit (re-checked by Compliance) or reject with a reason. */
export function ApprovalPanel({ payload, onDecide, busy, onRegenerateParagraph }: {
  payload: Payload;
  onDecide: (d: Decision) => void;
  busy: boolean;
  onRegenerateParagraph?: (claimIndex: number) => Promise<string>;
}) {
  const isProposal = payload.kind === "proposal_approval";
  const original = isProposal ? payload.draft.cover_letter : payload.draft.text;
  const [text, setText] = useState(original);
  const [reason, setReason] = useState("");
  const [paragraphIndex, setParagraphIndex] = useState(0);
  const [regenerating, setRegenerating] = useState(false);
  const [regenerationError, setRegenerationError] = useState("");
  const can = (a: string) => payload.allowed_actions.includes(a) && !busy && !regenerating;
  const verdicts = isProposal ? payload.claim_verification : [];
  const claims = payload.draft.claims;
  const coverClaims = isProposal ? payload.draft.claims.filter((c) => c.section === "cover") : [];

  async function regenerate() {
    if (!onRegenerateParagraph || text !== original) return;
    setRegenerating(true);
    setRegenerationError("");
    try {
      const rewritten = await onRegenerateParagraph(paragraphIndex);
      const paragraphs = text.split(/\n\s*\n/);
      paragraphs[paragraphIndex] = rewritten;
      setText(paragraphs.join("\n\n"));
    } catch (e) {
      setRegenerationError((e as Error).message);
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))" }}>
      <section className="card" aria-label="Draft">
        <h2>{isProposal ? "Cover letter" : "Reply"}</h2>
        <label htmlFor="draft-text" className="muted">Edit the text, then “Save edit” (Compliance re-checks it)</label>
        <textarea id="draft-text" value={text} onChange={(e) => setText(e.target.value)} />
        {isProposal && onRegenerateParagraph && <div className="row" style={{ marginTop: ".6rem" }}>
          <label htmlFor="paragraph-to-regenerate">Paragraph</label>
          <select id="paragraph-to-regenerate" value={paragraphIndex} onChange={(e) => setParagraphIndex(Number(e.target.value))}>
            {coverClaims.map((claim, index) => <option key={index} value={index}>{index + 1}. {claim.text.slice(0, 70)}</option>)}
          </select>
          <button type="button" disabled={!can("edit") || text !== original || regenerating ||
            coverClaims[paragraphIndex]?.kind !== "claim" || !coverClaims[paragraphIndex]?.evidence_ids.length}
            onClick={regenerate}>{regenerating ? "Regenerating…" : "Regenerate paragraph"}</button>
        </div>}
        {text !== original && isProposal && <p className="muted">Save this edit before regenerating another paragraph.</p>}
        {regenerationError && <p role="alert" className="err">{regenerationError}</p>}
        <div className="row" style={{ marginTop: ".6rem" }}>
          <button className="primary" disabled={!can("approve") || text !== original} onClick={() => onDecide({ action: "approve" })}>Approve</button>
          <button disabled={!can("edit") || text === original} onClick={() => onDecide({ action: "edit", edited_cover_letter: text })}>Save edit</button>
        </div>
        <div className="row" style={{ marginTop: ".6rem" }}>
          <label htmlFor="reject-reason" className="muted">Reject reason</label>
          <input id="reject-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="why?" />
          <button className="danger" disabled={!can("reject") || !reason.trim()} onClick={() => onDecide({ action: "reject", reason })}>Reject</button>
        </div>
        {text !== original && <p className="muted">Unsaved changes: save the edit before approving.</p>}
        {payload.edit_diff && <details><summary>Changes from your last edit</summary><pre>{payload.edit_diff}</pre></details>}
        {payload.blocking_reasons.length > 0 && (
          <div role="alert" className="err" data-testid="blocked"><strong>Blocked, cannot approve:</strong>
            <ul>{payload.blocking_reasons.map((r) => <li key={r}>{r}</li>)}</ul></div>)}
        {payload.error && <p role="alert" className="err">{payload.error}</p>}
      </section>

      <section className="card" aria-label="Evidence per sentence">
        <h2>Every sentence and its evidence</h2>
        <p className="muted">Hover or focus a sentence. Green = supported, amber = partly, red = unsupported.</p>
        {claims.map((c, i) => <EvidenceHover key={i} claim={c} verdict={verdicts[i]} evidence={payload.evidence} />)}
      </section>

      <section className="card" aria-label="Checks">
        <h2>Checks</h2>
        {isProposal && <>
          <p><strong>Critic:</strong> {payload.critique ? (payload.critique.passed ? "passed" : "issues remain") : "n/a"}</p>
          <ul>{payload.critique?.issues.map((x) => <li key={x}>{x}</li>)}</ul>
          <p><strong>Risk:</strong> {payload.risk_report.score.toFixed(2)} {payload.risk_report.flags.join(", ")}</p>
          <p><strong>Price:</strong> {payload.price_quote.amount} {payload.price_quote.currency} <span className="muted">{payload.price_quote.rationale}</span></p>
          <p data-testid="dry-run"><strong>Dry run:</strong> sends this exactly, costs {payload.dry_run.connects_cost} Connects{payload.price_quote.affordable ? "" : " (not affordable)"}</p>
        </>}
        {!isProposal && <>
          <p><strong>Client wrote:</strong> “{payload.client_message}”</p>
          <p><strong>Intent:</strong> {payload.intent.intent}</p>
          {payload.draft.offered_slots.length > 0 && <p><strong>Offered slots:</strong> {payload.draft.offered_slots.join(", ")} <span className="muted">(a tentative hold is created only after you approve)</span></p>}
        </>}
        <p><strong>Compliance:</strong> {payload.compliance_verdict.passed ? "passed" : "blocked"}</p>
        <ul>{payload.compliance_verdict.violations.map((v, i) => <li key={i}>{v.rule}: {v.match} → {v.action}</li>)}</ul>
      </section>
    </div>
  );
}
