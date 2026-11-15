import type { ReactNode } from "react";

const TONE: Record<string, string> = { submitted: "ok", awaiting_approval: "warn", running: "warn", skipped: "", rejected: "", sent: "ok",
  flagged: "bad", failed: "bad", error: "bad", needs_attention: "bad", dead_letter: "bad", queued_degraded: "bad", bid: "ok", watch: "warn", skip: "" };

export const StatusBadge = ({ status }: { status: string }) => <span className={`badge ${TONE[status] ?? ""}`}>{status.replace(/_/g, " ")}</span>;
export const Loading = ({ what = "Loading" }: { what?: string }) => <p role="status" aria-live="polite" className="muted">{what}…</p>;
export const ErrorBox = ({ error, retry }: { error: { status?: number; message: string }; retry?: () => void }) => (
  <div role="alert" className="card err">
    <strong>{error.status === 503 ? "Marketplace unavailable" : "Something went wrong"}</strong>
    <div>{error.message}</div>
    {error.status === 503 && <div className="muted">Any queued analyses resume automatically when the marketplace is back.</div>}
    {retry && <button onClick={retry}>Try again</button>}
  </div>
);
export const Empty = ({ children }: { children: ReactNode }) => <p className="muted card">{children}</p>;
