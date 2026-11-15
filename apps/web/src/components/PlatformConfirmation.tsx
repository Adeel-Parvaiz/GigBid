import { useState } from "react";
import { api, unwrap, useLoad } from "../lib/http";

export function PlatformConfirmation({ runId }: { runId: string }) {
  const run = useLoad(() => unwrap(api.GET("/runs/{run_id}", { params: { path: { run_id: runId } } })));
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attachments, setAttachments] = useState("");
  const summary = run.data?.summary as Record<string, Record<string, unknown>> | undefined;
  const pending = summary?.submission ?? summary?.send_result;
  if (run.data?.status !== "awaiting_platform_confirmation" || !pending?.platform_action_id) return null;
  return <section className="card" aria-label="Confirm on Upwork">
    <h2>Confirm on Upwork</h2>
    <p>Your GigBid approval prepared this action. It has not been submitted or sent on Upwork.</p>
    <details open><summary>Review the full action</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(pending.platform_preview, null, 2)}</pre></details>
    <label><input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)} /> I reviewed this action and authorize executing it on my Upwork account.</label>
    {run.data.kind === "bid" && <p><label>Would you like to attach files or profile highlights?<br /><select value={attachments} onChange={e => setAttachments(e.target.value)}><option value="">Choose an answer</option><option value="none">No files or highlights</option><option value="wanted">Yes, attach files or highlights</option></select></label>{attachments === "wanted" && <span> Complete attachment upload/highlight selection on Upwork before confirming; this interface does not upload files yet.</span>}</p>}
    <p>Proposal confirmation may spend the Connects shown in the preview. Message confirmation sends the displayed text.</p>
    <button disabled={!checked || busy || (run.data.kind === "bid" && attachments !== "none")} onClick={async () => {
      setBusy(true); setError("");
      try {
        await unwrap(api.POST("/runs/{run_id}/platform-confirmation", { params: { path: { run_id: runId } }, body: { review_hash: String(pending.review_hash), confirm_on_upwork: true, attachments_choice: attachments || null } }));
        window.location.reload();
      } catch (e) { setError((e as Error).message); }
      finally { setBusy(false); }
    }}>{busy ? "Confirming…" : "Confirm this action on Upwork"}</button>
    {error && <p role="alert">{error}</p>}
  </section>;
}
