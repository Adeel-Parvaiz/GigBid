import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading } from "../../components/Status";
import { api, unwrap, useLoad } from "../../lib/http";

const OUTCOMES = ["viewed", "replied", "interview", "hired", "lost"] as const;

export default function PipelinePage() {
  const { data, error, loading, reload } = useLoad(() => unwrap(api.GET("/pipeline")));
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  const cols = data?.columns ?? {};
  async function mark(run_id: string, outcome: (typeof OUTCOMES)[number]) {
    await api.POST("/runs/{run_id}/outcome", { params: { path: { run_id } }, body: { outcome } }); reload();
  }
  if (Object.values(cols).every((c) => c.length === 0)) return <><h1>Pipeline</h1><Empty>No proposals yet. Approve one from the inbox.</Empty></>;
  return (
    <>
      <h1>Pipeline</h1>
      <div className="kanban" role="list">
        {Object.entries(cols).map(([name, cards]) => (
          <section key={name} className="card" role="listitem" aria-label={name}>
            <h2 style={{ textTransform: "capitalize", marginTop: 0 }}>{name} <span className="badge">{cards.length}</span></h2>
            {cards.map((r) => (
              <article key={r.run_id} className="pipeline-item">
                <Link to={`/runs/${r.run_id}`}>{r.target}</Link>
                <div><span className="badge">{r.status.replace(/_/g, " ")}</span></div>
                {name === "submitted" || name === "viewed" || name === "replied" || name === "interview" ? (
                  <label className="muted" style={{ display: "block" }}>Marketplace event
                    <select defaultValue="" onChange={(e) => e.target.value && mark(r.run_id, e.target.value as (typeof OUTCOMES)[number])}>
                      <option value="">move to…</option>{OUTCOMES.map((o) => <option key={o}>{o}</option>)}</select></label>) : null}
              </article>))}
          </section>))}
      </div>
      <p className="muted">Events come from the marketplace; the select simulates them for the sample marketplace.</p>
    </>
  );
}
