import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BriefcaseBusiness, Search } from "lucide-react";
import { Empty, ErrorBox, Loading, StatusBadge } from "../../components/Status";
import { api, unwrap, useLoad } from "../../lib/http";

export default function InboxPage() {
  const nav = useNavigate();
  const { data, error, loading, reload } = useLoad(() => unwrap(api.GET("/jobs")));
  const [q, setQ] = useState(""); const [hideSkipped, setHide] = useState(false);
  useEffect(() => {
    window.addEventListener("gigbid:marketplace-restored", reload);
    return () => window.removeEventListener("gigbid:marketplace-restored", reload);
  }, [reload]);
  async function analyse(id: string) {
    const run = await unwrap(api.POST("/jobs/{job_id}/runs", { params: { path: { job_id: id } } }));
    nav(`/runs/${run.run_id}`);
  }
  if (loading) return <Loading what="Loading jobs" />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  const jobs = (data ?? []).filter((j) => j.title.toLowerCase().includes(q.toLowerCase()) && !(hideSkipped && j.recommended_action === "skip"));
  return (
    <>
      <div className="page-heading">
        <div><h1>Job inbox</h1><p>Review marketplace opportunities and decide what deserves your attention.</p></div>
        <span className="badge"><BriefcaseBusiness size={13} />{data?.length ?? 0} available</span>
      </div>
      <div className="filter-bar">
        <label className="search-field"><Search size={16} /><input aria-label="Filter jobs" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search job titles" /></label>
        <label className="row"><input type="checkbox" checked={hideSkipped} onChange={(e) => setHide(e.target.checked)} /> Hide recommended skips</label>
      </div>
      {jobs.length === 0 ? <Empty>No jobs match your filters.</Empty> : (
        <div className="job-listing-grid">
          {jobs.map((j) => (
            <article key={j.job_id} className="card job-card" data-testid="job-card">
              <div className="row">
                <span className="badge">{j.client_id}</span>
                {j.recommended_action && <StatusBadge status={j.recommended_action} />}
                {j.risk_score != null && <span className={`badge ${j.risk_score > 0.5 ? "bad" : j.risk_score > 0.2 ? "warn" : "ok"}`}>risk {j.risk_score.toFixed(2)}</span>}
              </div>
              <h3><Link to={`/jobs/${j.job_id}`}>{j.title}</Link></h3>
              {j.description && <p className="job-description-preview">{j.description}</p>}
              <div className="job-meta">
                <span>{j.budget_max == null ? "Budget not listed" : `Budget up to $${j.budget_max.toLocaleString()}`}</span>
                <span>{j.connects_cost == null ? "Connects cost after analysis" : `${j.connects_cost} Connects`}</span>
                {j.price != null && <span>Suggested bid ${j.price.toLocaleString()}</span>}
              </div>
              {j.required_skills.length > 0 && <div className="row">{j.required_skills.slice(0, 5).map((skill) => <span className="badge" key={skill}>{skill}</span>)}</div>}
              <div className="job-card-footer">
                <span className="muted">{j.fit_score == null ? "Fit not yet measured" : `Fit ${j.fit_score.toFixed(2)}`}</span>
                {j.latest_run ? <Link to={`/runs/${j.latest_run.run_id}`}>View run <ArrowRight size={14} /></Link>
                  : <button className="primary" onClick={() => analyse(j.job_id)}>Analyse <ArrowRight size={14} /></button>}
              </div>
            </article>))}
        </div>)}
    </>
  );
}
