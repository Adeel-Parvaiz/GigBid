import { ErrorBox, Loading } from "../../components/Status";
import { api, unwrap, useLoad } from "../../lib/http";

export default function AnalyticsPage() {
  const { data, error, loading, reload } = useLoad(() => unwrap(api.GET("/analytics")));
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  const a = data!;
  const ms = (v: number | null) => (v == null ? "n/a" : `${Math.round(v)} ms`);
  const number = (v: number | null, digits = 0) => v == null ? "n/a" : v.toFixed(digits);
  const usd = (v: number | null) => v == null ? "n/a" : `$${v.toFixed(6)}`;
  return (
    <>
      <div className="page-heading"><div><h1>Analytics</h1><p>Measured runs, proposal costs and marketplace outcomes.</p></div></div>
      <div className="grid">
        <div className="card metric-card"><div className="metric-label">Runs</div><div className="metric-value">{a.runs}</div>{Object.entries(a.by_status).map(([k, v]) => <div key={k}>{k}: {v}</div>)}</div>
        <div className="card metric-card"><div className="metric-label">Connects spent</div><div className="metric-value" data-testid="connects">{a.connects_spent}</div></div>
        <div className="card metric-card"><div className="metric-label">Latency per run</div><div className="metric-value">{ms(a.latency_ms_p50)}</div><p className="metric-note">p50 · p95 {ms(a.latency_ms_p95)}</p></div>
        <div className="card"><h2>Token usage</h2>
          <p>Jobs analyzed: {a.jobs_analyzed} · {number(a.average_tokens_per_job)} tokens/job</p>
          <p>Proposals: {a.proposals} · {number(a.average_tokens_per_proposal)} tokens/proposal</p>
          <p>{number(a.average_output_tokens_per_second, 1)} output tokens/sec</p>
        </div>
        <div className="card metric-card"><div className="metric-label">Cost per proposal (USD)</div><div className="metric-value">{usd(a.average_cost_per_proposal_usd)}</div>
          <p className="muted">{a.priced_proposals} priced · {a.unpriced_proposals} unpriced. Missing model pricing or exact provider usage is shown as n/a, never as $0.</p>
          {a.hardware_note && <p className="muted">{a.hardware_note}</p>}
        </div>
        <div className="card"><h2>Top skip reasons</h2>{a.top_skip_reasons.length ? <ul>{a.top_skip_reasons.map(([r, n]) => <li key={r}>{n}× {r}</li>)}</ul> : <p className="muted">none yet</p>}</div>
        <div className="card"><h2>Top rejection reasons</h2>{a.top_rejection_reasons.length ? <ul>{a.top_rejection_reasons.map(([r, n]) => <li key={r}>{n}× {r}</li>)}</ul> : <p className="muted">none yet</p>}</div>
        <div className="card"><h2>Reply rate by category</h2>{Object.keys(a.reply_rate_by_category).length ? <ul>{Object.entries(a.reply_rate_by_category).map(([c, v]) => <li key={c}>{c}: {JSON.stringify(v)}</li>)}</ul> : <p className="muted">Shown once a category has enough outcomes.</p>}</div>
      </div>
      <section className="card" style={{ marginTop: ".8rem" }} aria-label="Run costs and traces">
        <h2>Per-run usage and traces</h2>
        {a.run_metrics.length ? <table>
          <thead><tr><th>Job / run</th><th>Status</th><th>Tokens<br />(input / output)</th><th>Output tok/s</th><th>API cost USD</th><th>Latency</th><th>Trace</th></tr></thead>
          <tbody>{a.run_metrics.map((r) => <tr key={r.run_id}>
            <td><strong>{r.target}</strong><br /><span className="muted">{r.run_id}{r.proposal ? " · proposal" : r.job_analyzed ? " · analyzed" : ""}</span></td>
            <td>{r.status}</td>
            <td>{r.usage_exact ? "" : "~"}{r.tokens_used.toLocaleString()}<br /><span className="muted">{r.input_tokens.toLocaleString()} / {r.output_tokens.toLocaleString()}</span></td>
            <td>{number(r.output_tokens_per_second, 1)}</td>
            <td>{usd(r.cost_usd)}</td>
            <td>{ms(r.latency_ms)}</td>
            <td><a href={`/runs/${encodeURIComponent(r.run_id)}`} aria-label={`Open trace ${r.trace_id}`}>{r.trace_id}</a></td>
          </tr>)}</tbody>
        </table> : <p className="muted">Run a job to see token usage and its trace link.</p>}
      </section>
    </>
  );
}
