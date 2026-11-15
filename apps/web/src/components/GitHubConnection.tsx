import { useEffect, useState } from "react";
import { api, unwrap, useLoad } from "../lib/http";

export function GitHubConnection() {
  const connection = useLoad(() => unwrap(api.GET("/connections/github")));
  const imports = useLoad(() => unwrap(api.GET("/connections/github/imports")));
  const [owner, setOwner] = useState(""); const [repo, setRepo] = useState("");
  const [authorship, setAuthorship] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  useEffect(() => { if (connection.data?.login) setOwner(connection.data.login); }, [connection.data?.login]);
  useEffect(() => {
    if (!["connecting", "awaiting_authorization"].includes(connection.data?.status ?? "")) return;
    const timer = setInterval(connection.reload, 3000); return () => clearInterval(timer);
  }, [connection.data?.status, connection.reload]);
  async function connect() {
    const popup = window.open("about:blank", "gigbid-github-oauth"); setBusy(true); setError("");
    try {
      const result = await unwrap(api.POST("/connections/github/authorize"));
      if (result.authorization_url) { if (popup) { popup.opener = null; popup.location.href = result.authorization_url; } else window.location.assign(result.authorization_url); }
      else popup?.close();
      connection.reload();
    } catch (e) { popup?.close(); setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="card" aria-label="GitHub connection">
    <h2>GitHub repositories</h2>
    <p>Connect GitHub’s official MCP server in read-only mode. It cannot modify repositories or create issues or pull requests.</p>
    <p>Authorization requests read-only profile access. No repository write permission is requested; imports read public repositories only.</p>
    <p role="status">{connection.data?.connected ? `Connected as ${connection.data.login}` : `GitHub: ${connection.data?.status ?? "disconnected"}`}</p>
    <button disabled={busy} onClick={connect}>{busy ? "Connecting…" : "Connect GitHub"}</button>
    {connection.data?.authorization_message && <p role="status">{connection.data.authorization_message}</p>}
    {connection.data?.authorization_url && <p><a href={connection.data.authorization_url} target="_blank" rel="noopener noreferrer">Finish GitHub authorization</a></p>}
    {connection.data?.connected && <>
      <button onClick={async () => { await api.DELETE("/connections/github"); connection.reload(); }}>Disconnect GitHub</button>
      <p><label>Repository owner<input value={owner} onChange={e => setOwner(e.target.value)} /></label></p>
      <p><label>Repository name<input value={repo} onChange={e => setRepo(e.target.value)} placeholder="my-project" /></label></p>
      <label><input type="checkbox" checked={authorship} onChange={e => setAuthorship(e.target.checked)} /> I confirm this repository represents my own work and may be used as portfolio evidence.</label>
      <button disabled={!authorship || !owner || !repo || busy} onClick={async () => {
        setBusy(true); setError("");
        try { await unwrap(api.POST("/connections/github/imports", { body: { owner, repo, path: "README.md", authorship_confirmed: true } })); imports.reload(); }
        catch (e) { setError((e as Error).message); } finally { setBusy(false); }
      }}>Import README</button>
    </>}
    <p className="muted">Public-repository access only. Repository text is source evidence, not proof of client outcomes. Reconnect GitHub after an API restart.</p>
    {imports.data && <p>{imports.data.items.length} repository records saved for your account.</p>}
    {(error || connection.error) && <p role="alert">{error || connection.error?.message}</p>}
  </section>;
}
