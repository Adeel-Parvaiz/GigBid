import { Link, useNavigate, useParams } from "react-router-dom";
import { Empty, ErrorBox, Loading, StatusBadge } from "../../../components/Status";
import { api, unwrap, useLoad } from "../../../lib/http";
import type { Evidence } from "../../../types";

type Sum = { job_spec?: { title: string; deliverables: string[]; required_skills: string[]; budget_min?: number; budget_max?: number }; risk_report?: { score: number; flags: string[]; explanation: string };
  fit_report?: { score: number; matched_skills: string[]; missing_skills: string[]; evidence_ids: string[];
    requirement_evidence?: { requirement: string; evidence_ids: string[]; matched: boolean }[]; variant: string }; decision?: { action: string; reasons: string[] };
  price_quote?: { amount: number; currency: string; rationale: string; connects_cost: number }; evidence?: Evidence[] };

export default function JobDetailPage() {
  const { id = "" } = useParams(); const nav = useNavigate();
  const { data, error, loading, reload } = useLoad(async () => {
    const jobs = await unwrap(api.GET("/jobs"));
    const job = jobs.find((j) => j.job_id === id);
    const run = job?.latest_run ? await unwrap(api.GET("/runs/{run_id}", { params: { path: { run_id: job.latest_run.run_id } } })) : null;
    return { job, run };
  }, [id]);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  if (!data?.job) return <Empty>Job not found.</Empty>;
  const { job, run } = data; const s = (run?.summary ?? {}) as Sum;
  async function analyse() { const r = await unwrap(api.POST("/jobs/{job_id}/runs", { params: { path: { job_id: id } } })); nav(`/runs/${r.run_id}`); }
  return (
    <>
      <div className="page-heading"><div><h1>{job.title}</h1><p>{job.client_id} · {job.budget_max == null ? "Budget not listed" : `Budget up to $${job.budget_max.toLocaleString()}`}</p></div>
        {job.recommended_action && <StatusBadge status={job.recommended_action} />}
      </div>
      {job.description && <section className="card job-description">
        <h2>Job description</h2><p>{job.description}</p>
        <div className="row">{job.required_skills.map((skill) => <span className="badge" key={skill}>{skill}</span>)}</div>
      </section>}
      {!run && <p><button className="primary" onClick={analyse}>Analyse this job</button></p>}
      {run && <p className="row"><StatusBadge status={run.status} /><Link to={`/runs/${run.run_id}`}>run viewer</Link>{run.pending && <Link to={`/studio/${run.run_id}`}>open proposal studio</Link>}</p>}
      {s.decision && <section className="card"><h2>Bid or skip: <StatusBadge status={s.decision.action} /></h2><ul>{s.decision.reasons.map((r) => <li key={r}>{r}</li>)}</ul></section>}
      <div className="grid" style={{ marginTop: ".8rem" }}>
        {s.job_spec && <section className="card"><h2>JobSpec</h2><ul>{s.job_spec.deliverables.map((d) => <li key={d}>{d}</li>)}</ul>
          <p className="muted">Skills: {s.job_spec.required_skills.join(", ")}</p></section>}
        {s.risk_report && <section className="card"><h2>Risk <span className="badge">{s.risk_report.score.toFixed(2)}</span></h2>
          <div className="row">{s.risk_report.flags.length ? s.risk_report.flags.map((f) => <span key={f} className="badge bad">{f}</span>) : <span className="badge ok">no flags</span>}</div></section>}
        {s.price_quote && <section className="card"><h2>Price</h2><p>{s.price_quote.amount} {s.price_quote.currency}</p><p className="muted">{s.price_quote.rationale}</p><p>{s.price_quote.connects_cost} Connects</p></section>}
      </div>
      {s.fit_report && (
        <section className="card" style={{ marginTop: ".8rem" }} aria-label="Requirement to evidence matrix">
          <h2>Requirements → evidence <span className="badge">fit {s.fit_report.score.toFixed(2)}</span> <span className="muted">retrieval {s.fit_report.variant}</span></h2>
          <p className="muted">Evidence is retrieved separately for each requirement. A retrieved candidate is not proof by itself; check the cited work and verifier verdict.</p>
          <table><thead><tr><th>Requirement</th><th>Proof in your portfolio</th></tr></thead><tbody>
            {(s.fit_report.requirement_evidence ?? []).map((item) => {
              const evidenceById = new Map((s.evidence ?? []).map((e) => [e.evidence_id, e]));
              const candidates = item.evidence_ids.map((evidenceId) => evidenceById.get(evidenceId))
                .filter((e): e is Evidence => e !== undefined);
              return <tr key={item.requirement}>
                <td>{item.requirement}<br /><span className={`badge ${item.matched ? "ok" : "warn"}`}>{item.matched ? "text match" : "review candidates"}</span></td>
                <td>{candidates.length ? candidates.map((e) => <div key={e.evidence_id}><code>{e.evidence_id}</code> {e.title}<p className="muted">{e.summary}</p></div>)
                  : <span className="err">no evidence found: do not claim it</span>}</td>
              </tr>;
            })}
          </tbody></table>
        </section>)}
    </>
  );
}
