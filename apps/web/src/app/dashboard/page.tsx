import { ArrowRight, BadgeCheck, Bot, BriefcaseBusiness, Coins, GitBranch, Gauge, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading, StatusBadge } from "../../components/Status";
import { api, unwrap, useLoad } from "../../lib/http";

export default function DashboardPage() {
  const { data, error, loading, reload } = useLoad(async () => {
    const [analytics, jobs, pipeline, health] = await Promise.all([
      unwrap(api.GET("/analytics")),
      unwrap(api.GET("/jobs")),
      unwrap(api.GET("/pipeline")),
      unwrap(api.GET("/health")),
    ]);
    return { analytics, jobs, pipeline, health };
  });
  if (loading) return <Loading what="Loading workspace" />;
  if (error) return <ErrorBox error={error} retry={reload} />;

  const { analytics, jobs, pipeline, health } = data!;
  const statuses = analytics.by_status;
  const pending = (statuses.awaiting_approval ?? 0) + (statuses.needs_attention ?? 0);
  const active = statuses.running ?? 0;
  const proposals = analytics.proposals;
  const actionableJobs = jobs.filter((job) => job.recommended_action !== "skip").slice(0, 3);
  const latestRuns = analytics.run_metrics.slice(0, 6);
  const pipelineCount = Object.values(pipeline.columns).reduce((sum, runs) => sum + runs.length, 0);

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Overview</h1>
          <p>Your freelance workflow, decisions and marketplace activity in one place.</p>
        </div>
        <Link to="/inbox"><button className="primary">Browse jobs <ArrowRight size={15} /></button></Link>
      </div>

      <section className="grid" aria-label="Workspace performance">
        <article className="card metric-card">
          <div className="metric-label"><BriefcaseBusiness size={16} />Jobs analyzed</div>
          <div className="metric-value">{analytics.jobs_analyzed.toLocaleString()}</div>
          <div className="metric-note">Across recorded agent runs</div>
        </article>
        <article className="card metric-card">
          <div className="metric-label"><BadgeCheck size={16} />Proposals created</div>
          <div className="metric-value">{proposals.toLocaleString()}</div>
          <div className="metric-note">{pending} awaiting action</div>
        </article>
        <article className="card metric-card">
          <div className="metric-label"><Coins size={16} />Connects tracked</div>
          <div className="metric-value">{analytics.connects_spent.toLocaleString()}</div>
          <div className="metric-note">Recorded spend; balance unavailable</div>
        </article>
        <article className="card metric-card">
          <div className="metric-label"><Bot size={16} />Agent activity</div>
          <div className="metric-value">{active ? `${active} running` : "Idle"}</div>
          <div className="metric-note">{analytics.runs.toLocaleString()} total runs · {pipelineCount} in pipeline</div>
        </article>
      </section>

      <section className="dashboard-columns">
        <div>
          <div className="section-title">
            <h2>Jobs to review</h2><Link to="/inbox">All jobs <ArrowRight size={14} /></Link>
          </div>
          {actionableJobs.length ? <div className="grid">
            {actionableJobs.map((job) => <article className="card job-card" key={job.job_id} data-testid="job-card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="badge">{job.client_id}</span>
                {job.recommended_action && <StatusBadge status={job.recommended_action} />}
              </div>
              <h3><Link to={`/jobs/${job.job_id}`}>{job.title}</Link></h3>
              {job.description && <p className="job-description-preview">{job.description}</p>}
              <div className="row">
                {job.budget_max != null && <span className="muted">Budget up to ${job.budget_max.toLocaleString()}</span>}
                {job.connects_cost != null && <span className="muted">{job.connects_cost} Connects</span>}
              </div>
              {job.required_skills.length > 0 && <div className="row">{job.required_skills.slice(0, 4).map((skill) => <span className="badge" key={skill}>{skill}</span>)}</div>}
              <div className="job-card-footer">
                <span className="muted">{job.fit_score == null ? "Fit not yet measured" : `Fit ${job.fit_score.toFixed(2)}`}</span>
                <Link to={job.latest_run ? `/runs/${job.latest_run.run_id}` : `/jobs/${job.job_id}`}>
                  {job.latest_run ? "View analysis" : "Review job"} <ArrowRight size={14} />
                </Link>
              </div>
            </article>)}
          </div> : <Empty>No jobs currently recommended for review.</Empty>}

          <div className="section-title">
            <h2>Latest agent runs</h2><Link to="/analytics">Usage and traces <ArrowRight size={14} /></Link>
          </div>
          {latestRuns.length ? <section className="card" aria-label="Latest agent runs">
            <table>
              <thead><tr><th>Job / thread</th><th>Status</th><th>Tokens</th><th>Trace</th></tr></thead>
              <tbody>{latestRuns.map((run) => <tr key={run.run_id}>
                <td><Link to={`/runs/${encodeURIComponent(run.run_id)}`}>{run.target}</Link><br /><span className="muted">{run.kind === "bid" ? "Job analysis" : "Client conversation"}</span></td>
                <td><StatusBadge status={run.status} /></td>
                <td>{run.usage_exact ? "" : "~"}{run.tokens_used.toLocaleString()}</td>
                <td><Link to={`/runs/${encodeURIComponent(run.run_id)}`} aria-label={`Open trace ${run.trace_id}`}>{run.trace_id}</Link></td>
              </tr>)}</tbody>
            </table>
          </section> : <Empty>No agent runs recorded yet.</Empty>}
        </div>

        <aside className="dashboard-aside">
          <section className="card" aria-label="Marketplace status">
            <div className="section-title" style={{ marginTop: 0 }}>
              <h2><Gauge size={17} /> Marketplace</h2>
              <span className={`badge ${health.marketplace === "ok" ? "ok" : "bad"}`}>{health.marketplace}</span>
            </div>
            <p className="muted">API {health.api}. Marketplace state is polled live.</p>
            {health.queued_degraded_runs > 0 && <p className="badge warn">{health.queued_degraded_runs} queued run{health.queued_degraded_runs === 1 ? "" : "s"}</p>}
            <Link to="/settings">Connection settings <ArrowRight size={14} /></Link>
          </section>
          <section className="card" aria-label="Proposal pipeline">
            <div className="section-title" style={{ marginTop: 0 }}>
              <h2><GitBranch size={17} /> Pipeline</h2><Link to="/pipeline">Open <ArrowRight size={14} /></Link>
            </div>
            {Object.entries(pipeline.columns).map(([name, runs]) => <div className="pipeline-count" key={name}>
              <span>{name.replace(/_/g, " ")}</span><strong>{runs.length}</strong>
            </div>)}
            {!Object.keys(pipeline.columns).length && <p className="muted">No proposal activity yet.</p>}
          </section>
          <section className="card dashboard-note">
            <ShieldAlert size={18} />
            <p>Every proposal remains gated for your review. GigBid does not auto-submit proposals.</p>
          </section>
        </aside>
      </section>
    </>
  );
}
