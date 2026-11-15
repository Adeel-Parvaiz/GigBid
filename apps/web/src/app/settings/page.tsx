import { FormEvent, useEffect, useState } from "react";
import { ErrorBox, Loading } from "../../components/Status";
import { api, unwrap, useLoad } from "../../lib/http";
import { UpworkConnection } from "../../components/UpworkConnection";
import { GitHubConnection } from "../../components/GitHubConnection";
import { PortfolioIngestion } from "../../components/PortfolioIngestion";

export default function SettingsPage() {
  const s = useLoad(() => unwrap(api.GET("/settings")));
  const m = useLoad(() => unwrap(api.GET("/memory")));
  const [rate, setRate] = useState(""); const [minb, setMinb] = useState(""); const [conn, setConn] = useState(""); const [auto, setAuto] = useState(true);
  const [search, setSearch] = useState(""); const [saved, setSaved] = useState("");
  useEffect(() => { const d = s.data; if (d) { setRate(String(d.hourly_rate_usd ?? "")); setMinb(String(d.minimum_project_budget_usd ?? "")); setConn(String(d.weekly_connects_budget ?? "")); setAuto(d.auto_skip_low_fit ?? true); } }, [s.data]);
  if (s.loading || m.loading) return <Loading />;
  if (s.error) return <ErrorBox error={s.error} retry={s.reload} />;
  async function save(e: FormEvent) {
    e.preventDefault();
    await unwrap(api.PUT("/settings", { body: { hourly_rate_usd: rate ? Number(rate) : null, minimum_project_budget_usd: minb ? Number(minb) : null, weekly_connects_budget: conn ? Number(conn) : null, auto_skip_low_fit: auto } }));
    setSaved("Saved"); s.reload();
  }
  return (
    <>
      <div className="page-heading"><div><h1>Settings</h1><p>Manage your profile, marketplace connections and automation preferences.</p></div></div>
      <div className="grid">
        <UpworkConnection />
        <GitHubConnection />
        <PortfolioIngestion />
        <form className="card" onSubmit={save} aria-label="Rates, budgets and autonomy">
          <h2>Rates and budgets</h2>
          <p><label>Hourly rate (USD)<br /><input type="number" value={rate} onChange={(e) => setRate(e.target.value)} /></label></p>
          <p><label>Minimum project budget (USD)<br /><input type="number" value={minb} onChange={(e) => setMinb(e.target.value)} /></label></p>
          <p><label>Weekly Connects budget<br /><input type="number" value={conn} onChange={(e) => setConn(e.target.value)} /></label></p>
          <p><label><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> Auto-skip low-fit jobs</label><br /><span className="muted">{s.data?.autonomy_note}</span></p>
          <button className="primary">Save</button> <span role="status">{saved}</span>
        </form>
        <section className="card" aria-label="Saved searches">
          <h2>Saved searches</h2>
          <ul>{s.data?.saved_searches?.map((q) => <li key={q}>{q} <button aria-label={`remove ${q}`} onClick={async () => { await api.DELETE("/settings/searches/{query}", { params: { path: { query: q } } }); s.reload(); }}>×</button></li>)}</ul>
          <form className="row" onSubmit={async (e) => { e.preventDefault(); if (search) { await api.POST("/settings/searches/{query}", { params: { path: { query: search } } }); setSearch(""); s.reload(); } }}>
            <input aria-label="new saved search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="keyword" /><button>Add</button></form>
          <p className="muted">The worker scouts these on a schedule (read-only).</p>
        </section>
        <section className="card" aria-label="What GigBid has learned">
          <h2>What GigBid has learned</h2>
          {m.data?.style.length ? <ul>{m.data.style.map((r) => (
            <li key={String(r.id)}>{String(r.rule)} <span className="muted">(from {(r.learned_from_jobs as string[]).length} jobs)</span>{" "}
              <button aria-label={`forget ${String(r.id)}`} onClick={async () => { await api.DELETE("/memory/style/{rule_id}", { params: { path: { rule_id: String(r.id) } } }); m.reload(); }}>Forget</button></li>))}</ul>
            : <p className="muted">Nothing yet. A style rule appears only after the same edit recurs on several different jobs.</p>}
          <p className="muted">Outcome memory</p>
          {Object.entries(m.data?.outcome ?? {}).length ? <ul>{Object.entries(m.data?.outcome ?? {}).map(([category, value]) => (
            <li key={category}>{category}: {JSON.stringify(value)}{" "}
              <button aria-label={`forget outcome ${category}`} onClick={async () => { await api.DELETE("/memory/outcome/{category}", { params: { path: { category } } }); m.reload(); }}>Forget</button>
            </li>))}</ul> : <p className="muted">Hidden until a category has enough results.</p>}
        </section>
      </div>
    </>
  );
}
