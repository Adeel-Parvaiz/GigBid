import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApprovalPanel, type Decision } from "../../../components/ApprovalPanel";
import { Empty, ErrorBox, Loading, StatusBadge } from "../../../components/Status";
import { api, unwrap, useLoad } from "../../../lib/http";
import type { Payload } from "../../../types";

/** Proposal studio (and message approval). The pending payload is read from the server, so a refresh never loses it. */
export default function StudioPage() {
  const { id = "" } = useParams(); const nav = useNavigate();
  const { data, error, loading, reload } = useLoad(() => unwrap(api.GET("/runs/{run_id}", { params: { path: { run_id: id } } })), [id]);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  if (!data) return null;
  const payload = data.pending as unknown as Payload | null;
  async function decide(d: Decision) {
    setBusy(true); setErr("");
    try { await unwrap(api.POST("/runs/{run_id}/approval", { params: { path: { run_id: id } }, body: d })); nav(`/runs/${id}`); }
    catch (e) { setErr((e as Error).message); reload(); } finally { setBusy(false); }
  }
  async function regenerateParagraph(claimIndex: number) {
    const result = await unwrap(api.POST("/runs/{run_id}/regenerate-paragraph", {
      params: { path: { run_id: id } }, body: { claim_index: claimIndex },
    }));
    return result.text;
  }
  return (
    <>
      <h1>{payload?.kind === "message_approval" ? "Reply studio" : "Proposal studio"} <StatusBadge status={data.status} /></h1>
      {!payload ? <Empty>Nothing is waiting for approval on this run. <Link to={`/runs/${id}`}>Open run viewer</Link></Empty>
        : <ApprovalPanel key={JSON.stringify(payload.draft)} payload={payload} onDecide={decide} busy={busy}
            onRegenerateParagraph={payload.kind === "proposal_approval" ? regenerateParagraph : undefined} />}
      {err && <p role="alert" className="err">{err}</p>}
    </>
  );
}
