import { FormEvent, useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, BASE, tokenStore, unwrap } from "../../lib/http";

export default function LoginPage() {
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [rate, setRate] = useState("25"); const [budget, setBudget] = useState("40");
  const [personas, setPersonas] = useState<{ freelancer_id: string; display_name: string }[]>([]);
  const [persona, setPersona] = useState("");
  useEffect(() => { fetch(`${BASE}/auth/personas`).then((r) => r.json()).then((p) => { setPersonas(p); setPersona(p[0]?.freelancer_id ?? ""); }).catch(() => undefined); }, []);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const t = mode === "login"
        ? await unwrap(api.POST("/auth/login", { body: { email, password } }))
        : await unwrap(api.POST("/auth/register", { body: { email, password, freelancer_id: persona } }));
      tokenStore.set(t.token);
      if (mode === "register") await unwrap(api.PUT("/settings", { body: { hourly_rate_usd: Number(rate), weekly_connects_budget: Number(budget) } }));
      nav("/inbox");
    } catch (e2) { setErr((e2 as Error).message); } finally { setBusy(false); }
  }
  return (
    <main className="auth-page">
      <div>
      <div className="auth-brand"><span className="brand-mark"><Activity size={18} /></span><h1>GigBid</h1></div>
      <form className="card auth-card" onSubmit={submit} aria-label={mode === "login" ? "Sign in" : "Create account"}>
        <h2>{mode === "login" ? "Sign in" : "Create your account"}</h2>
        <p className="auth-description">A clear view of your jobs, proposal decisions and client conversations.</p>
        <p><label>Email<br /><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: "100%" }} /></label></p>
        <p><label>Password<br /><input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} style={{ width: "100%" }} /></label></p>
        {mode === "register" && <>
          <p><label>Persona<br /><select value={persona} onChange={(e) => setPersona(e.target.value)}>{personas.map((p) => <option key={p.freelancer_id} value={p.freelancer_id}>{p.display_name}</option>)}</select></label></p>
          <p><label>Hourly rate (USD)<br /><input type="number" min={1} value={rate} onChange={(e) => setRate(e.target.value)} /></label></p>
          <p><label>Weekly Connects budget<br /><input type="number" min={0} value={budget} onChange={(e) => setBudget(e.target.value)} /></label></p>
          <p className="muted">Marketplace: sample simulator (GigSim/Upwork connect from Settings later). Add your own portfolio documents or authored-work imports in Settings; sample persona evidence is used until then.</p>
        </>}
        {err && <p role="alert" className="err">{err}</p>}
        <div className="row"><button className="primary" disabled={busy}>{mode === "login" ? "Sign in" : "Create account"}</button>
          <button type="button" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "Create account" : "I have an account"}</button></div>
      </form>
      </div>
    </main>
  );
}
