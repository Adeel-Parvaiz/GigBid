import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Check, Clock3, LoaderCircle } from "lucide-react";
import { api, streamRun } from "../lib/http";
import type { RunEvent } from "../types";
import { StatusBadge } from "./Status";

/** Live node-by-node progress from the LangGraph stream. Reconnects after an approval resumes the thread. */
export function RunTimeline({ runId, onSettled }: { runId: string; onSettled?: () => void }) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [status, setStatus] = useState("running");
  const [summary, setSummary] = useState<Record<string, unknown>>({});
  const [err, setErr] = useState("");
  const [confirmation, setConfirmation] = useState("");

  useEffect(() => {
    const ctl = new AbortController();
    let after = 0;
    (async () => {
      try {
        for (let round = 0; round < 50; round++) {
          for await (const ev of streamRun(runId, after, ctl.signal)) {
            after = ev.seq;
            setEvents((prev) => [...prev, ev]);
          }
          const { data } = await api.GET("/runs/{run_id}", { params: { path: { run_id: runId } } });
          if (!data) return;
          setStatus(data.status);
          const summary = data.summary as Record<string, unknown>;
          setSummary({ ...summary, trace_id: data.trace_id });
          const result = (summary.submission ?? summary.send_result) as Record<string, unknown> | undefined;
          if (typeof result?.confirmation_url === "string") {
            const url = new URL(result.confirmation_url);
            if (url.protocol === "https:" && (url.hostname === "upwork.com" || url.hostname.endsWith(".upwork.com"))) setConfirmation(url.href);
          }
          if (data.status !== "running") { onSettled?.(); return; }
          await new Promise((r) => setTimeout(r, 300));
        }
      } catch (e) { if (!ctl.signal.aborted) setErr(String(e)); }
    })();
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  const trace = events.find((e) => e.type === "started")?.trace_id;
  const last = events[events.length - 1];
  const traceNodes = Array.isArray(summary.trace) ? summary.trace.filter((item): item is { node: string; ms?: number; wrote?: string[] } =>
    typeof item === "object" && item !== null && typeof (item as { node?: unknown }).node === "string") as
      { node: string; ms?: number; wrote?: string[] }[] : [];
  const eventNodes = events.filter((event) => event.type === "node" && event.node);
  const traceByNode = new Map(traceNodes.map((item) => [item.node, item]));
  const nodeRows = eventNodes.length
    ? eventNodes.map((event) => {
      const traceNode = traceByNode.get(event.node!);
      return { node: event.node!, ms: traceNode?.ms, wrote: event.wrote?.length ? event.wrote : traceNode?.wrote };
    })
    : traceNodes;
  const uniqueNodes = nodeRows.filter((item, index, list) => list.findIndex((other) => other.node === item.node) === index);
  const tokensUsed = typeof summary.tokens_used === "number" ? summary.tokens_used : null;
  const formatNode = (node: string) => ({
    load_job: "Job inspection", load_thread: "Conversation context", analyst: "Research and evidence",
    risk: "Risk assessment", fit_matcher: "Skill matching", decide: "Bid-or-skip decision",
    pricing: "Pricing", writer: "Proposal draft", critic: "Critic review", verifier: "Claim verification",
    compliance: "Compliance validation", approval: "Human approval", submit: "Marketplace submission",
    draft_reply: "Reply draft", send_reply: "Send reply", learn: "Learning",
  }[node] ?? node.replace(/_/g, " "));
  const failed = last?.type === "error" || ["failed", "dead_letter"].includes(status);
  const decision = (summary.decision as { action?: string } | undefined)?.action;
  return (
    <section className="card run-monitor" aria-label="Run progress" aria-live="polite">
      <div className="run-monitor-heading">
        <div><h2>Execution monitor</h2><p className="muted">Graph stages recorded for this run</p></div>
        <StatusBadge status={status} />
      </div>
      <div className="run-metrics">
        {tokensUsed != null && <span><strong>{tokensUsed.toLocaleString()}</strong> tokens used</span>}
        {trace && <span>Trace <code data-testid="trace-id">{trace}</code></span>}
        {!trace && typeof summary.trace_id === "string" && <span>Trace <code data-testid="trace-id">{summary.trace_id}</code></span>}
      </div>
      {(status === "needs_attention" || status === "dead_letter") && <div role="alert" className="err">
        <strong>{status === "dead_letter" ? "Dead letter" : "Needs attention"}</strong>
        {Array.isArray(summary.errors) && summary.errors.map((message, index) =>
          typeof message === "string" ? <p key={index}>{message}</p> : null)}
        {typeof summary.failure_reason === "string" && <p>{summary.failure_reason}</p>}
      </div>}
      <ol className="timeline" data-testid="timeline">
        {uniqueNodes.map((item) => <li className="timeline-item" key={item.node}>
          <span className="timeline-icon complete"><Check size={15} /></span>
          <span className="timeline-name">{formatNode(item.node)} <code>{item.node}</code>
            {item.wrote?.length ? <span className="timeline-meta"> · updated {item.wrote.join(", ")}</span> : null}
          </span>
          <span className="timeline-meta">Completed{item.ms != null ? ` · ${Math.round(item.ms)} ms` : ""}</span>
        </li>)}
        {failed && <li className="timeline-item">
          <span className="timeline-icon failed"><AlertCircle size={15} /></span>
          <span className="timeline-name">Run failure
            {last?.message && <span className="timeline-meta"> · {last.message}</span>}
            {!last?.message && typeof summary.failure_reason === "string" && <span className="timeline-meta"> · {summary.failure_reason}</span>}
          </span>
          <span className="timeline-meta">Failed</span>
        </li>}
        {decision === "skip" && <li className="timeline-item">
          <span className="timeline-icon"><Clock3 size={15} /></span><span className="timeline-name">Marketplace submission <span className="timeline-meta">Skipped by bid decision</span></span><span className="timeline-meta">Skipped</span>
        </li>}
        {status === "running" && last?.type !== "interrupt" && <li className="timeline-item">
          <span className="timeline-icon running"><LoaderCircle size={15} /></span><span className="timeline-name">Processing next graph event</span><span className="timeline-meta">Running</span>
        </li>}
        {last?.type === "interrupt" && <li className="timeline-item">
          <span className="timeline-icon running"><Clock3 size={15} /></span><span className="timeline-name">Human approval</span><span className="timeline-meta">Pending</span>
        </li>}
      </ol>
      {!uniqueNodes.length && status !== "running" && <p className="muted">No graph-stage events are available for this run.</p>}
      {last?.type === "interrupt" && <p><Link className="primary" to={`/studio/${runId}`}>Awaiting your approval → open studio</Link></p>}
      {last?.type === "done" && <p>Finished: <StatusBadge status={last.status ?? "done"} /></p>}
      {err && <p role="alert" className="err">{err}</p>}
      {confirmation && <p>Your draft is ready. Review and confirm it separately on Upwork. <a href={confirmation} target="_blank" rel="noopener noreferrer">Open Upwork confirmation</a></p>}
    </section>
  );
}
