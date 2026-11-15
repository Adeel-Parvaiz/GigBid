import type { ClaimT, Evidence, Verdict } from "../types";

/** One proposal sentence. Hover or keyboard-focus shows the evidence behind it and the verifier's verdict. */
export function EvidenceHover({ claim, verdict, evidence }: { claim: ClaimT; verdict?: Verdict; evidence: Evidence[] }) {
  const items = evidence.filter((e) => claim.evidence_ids.includes(e.evidence_id));
  const label = verdict?.label ?? (claim.kind === "claim" ? "unverified" : "supported");
  return (
    <div className={`claim ${label}`} tabIndex={0} data-testid="claim" aria-label={`${claim.text} (${label})`}>
      {claim.text}
      <div className="pop" role="tooltip">
        <strong>{claim.kind === "claim" ? `Verifier: ${label}${verdict ? ` (${verdict.support})` : ""}` : `No experience claimed (${claim.kind})`}</strong>
        {verdict?.reason && <div className="muted">{verdict.reason}</div>}
        {items.length === 0 && claim.kind === "claim" && <div className="err">No evidence cited for this sentence.</div>}
        {items.map((e) => (
          <div key={e.evidence_id} style={{ marginTop: ".4rem" }}>
            <code>{e.evidence_id}</code> {e.title} <span className="badge">{e.outcome ?? e.type}</span>
            <div className="muted">{e.summary}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
