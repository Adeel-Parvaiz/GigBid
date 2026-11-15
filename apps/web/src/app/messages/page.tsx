import { Link, useNavigate } from "react-router-dom";
import { Empty, ErrorBox, Loading, StatusBadge } from "../../components/Status";
import { api, unwrap, useLoad } from "../../lib/http";

export default function MessagesPage() {
  const nav = useNavigate();
  const { data, error, loading, reload } = useLoad(() => unwrap(api.GET("/conversations")));
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} retry={reload} />;
  async function handle(thread_id: string) {
    const r = await unwrap(api.POST("/conversations/{thread_id}/runs", { params: { path: { thread_id } } })); nav(`/runs/${r.run_id}`);
  }
  if (!data?.length) return <><h1>Messages</h1><Empty>No client conversations.</Empty></>;
  return (
    <>
      <div className="page-heading"><div><h1>Messages</h1><p>Review client conversations and draft replies for approval.</p></div></div>
      <div className="grid">{data.map((t) => (
        <article key={t.thread_id} className="card">
          <div className="row" style={{ justifyContent: "space-between" }}><strong>{t.client_id}</strong><span className="muted">{t.thread_id}</span><span className="badge">Job {t.job_id}</span></div>
          <p className="message-preview">“{t.last_message}”</p>
          <div className="row">
            {t.latest_run ? <><StatusBadge status={t.latest_run.status} /><Link to={t.latest_run.status === "awaiting_approval" ? `/studio/${t.latest_run.run_id}` : `/runs/${t.latest_run.run_id}`}>open</Link></>
              : <button className="primary" onClick={() => handle(t.thread_id)}>Draft a reply</button>}
          </div>
        </article>))}</div>
    </>
  );
}
