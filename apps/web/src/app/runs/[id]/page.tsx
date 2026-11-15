import { useParams } from "react-router-dom";
import { useState } from "react";
import { RunTimeline } from "../../../components/RunTimeline";
import { PlatformConfirmation } from "../../../components/PlatformConfirmation";

export default function RunViewerPage() {
  const { id = "" } = useParams();
  const [revision, setRevision] = useState(0);
  return (<><div className="page-heading"><div><h1>Agent run</h1><p>Execution details · <code>{id}</code></p></div></div><RunTimeline runId={id} onSettled={() => setRevision(v => v + 1)} />
    <PlatformConfirmation key={revision} runId={id} />
    <p className="muted">Full trace: look up the trace id above in your tracing tool (Langfuse/LangSmith).</p></>);
}
