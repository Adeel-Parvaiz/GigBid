import { FormEvent, useEffect, useState } from "react";
import { BASE, tokenStore } from "../lib/http";

type SavedDocument = { document_id: string; filename: string; revision: number; chunk_count: number };
async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`${BASE}/portfolio${path}`, { method,
    headers: { Authorization: `Bearer ${tokenStore.get() ?? ""}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Check the document and required metadata.");
  return result;
}

export function PortfolioIngestion() {
  const [kind, setKind] = useState("case_study"); const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState(""); const [project, setProject] = useState(""); const [skills, setSkills] = useState("");
  const [date, setDate] = useState(""); const [industry, setIndustry] = useState(""); const [outcome, setOutcome] = useState("");
  const [synthetic, setSynthetic] = useState(false); const [confirmed, setConfirmed] = useState(false);
  const [owner, setOwner] = useState(""); const [repo, setRepo] = useState(""); const [path, setPath] = useState("README.md"); const [ref, setRef] = useState("");
  const [documents, setDocuments] = useState<SavedDocument[]>([]); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(""); const [status, setStatus] = useState(""); const [query, setQuery] = useState("");
  const [hits, setHits] = useState<{ evidence_id: string; summary: string; project?: string; source: string }[]>([]);
  const repository = kind === "readme" || kind === "code";
  const reload = async () => setDocuments((await request<{ items: SavedDocument[] }>("/documents")).items);
  useEffect(() => { reload().catch(e => setError(e.message)); }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setStatus("");
    try {
      const metadata = { title, project, skills: skills.split(",").map(x => x.trim()).filter(Boolean), date: date || null,
        client_industry: industry || null, outcome: outcome || null, provenance: synthetic ? "synthetic" : "user-upload", authorship_confirmed: confirmed };
      let body: unknown;
      if (repository) body = { owner, repo, path, ref: ref || null, kind, metadata };
      else {
        if (!file || file.size > 2_000_000) throw new Error("Choose a file of at most 2 MB.");
        const encoded = await new Promise<string>((resolve, reject) => { const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result).split(",")[1]); reader.onerror = () => reject(new Error("Cannot read file")); reader.readAsDataURL(file); });
        body = { filename: file.name, content_base64: encoded, kind, metadata };
      }
      const result = await request<{ unchanged: boolean; embedded_chunks: number; chunk_count: number }>(repository ? "/github" : "/documents", "POST", body);
      setStatus(result.unchanged ? "Already indexed; no changes." : `Indexed ${result.chunk_count} chunks; ${result.embedded_chunks} new or changed. Ready to search.`);
      await reload();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="card portfolio-ingestion" aria-label="Portfolio evidence">
    <h2>Add portfolio evidence</h2>
    <p>Upload work you may use as evidence. Repository files are read through your connected GitHub account; no repository data is changed.</p>
    <form onSubmit={save}>
      <p><label>Evidence type<select value={kind} onChange={e => setKind(e.target.value)}>
        <option value="cv">PDF or text CV</option><option value="case_study">Markdown case study</option>
        <option value="readme">GitHub README</option><option value="code">GitHub code file</option>
        <option value="review">Review (text or JSON)</option><option value="past_proposal">Past proposal (text or JSON)</option>
      </select></label></p>
      {repository ? <><p><label>Source owner<input required value={owner} onChange={e => setOwner(e.target.value)} /></label></p>
        <p><label>Source repository<input required value={repo} onChange={e => setRepo(e.target.value)} /></label></p>
        <p><label>Repository file path<input required value={path} onChange={e => setPath(e.target.value)} /></label></p>
        <p><label>Git ref (optional)<input value={ref} onChange={e => setRef(e.target.value)} placeholder="commit SHA, tag or branch" /></label></p></>
        : <p><label>Evidence file<input type="file" required accept={kind === "cv" ? ".pdf,.txt,.md" : ".md,.markdown,.txt,.json"} onChange={e => setFile(e.target.files?.[0] ?? null)} /></label></p>}
      <p><label>Evidence title<input required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} /></label></p>
      <p><label>Project<input required maxLength={200} value={project} onChange={e => setProject(e.target.value)} /></label></p>
      <p><label>Skills (comma separated)<input value={skills} onChange={e => setSkills(e.target.value)} /></label></p>
      <p><label>Work date (optional)<input type="date" value={date} onChange={e => setDate(e.target.value)} /></label></p>
      <p><label>Client industry (optional)<input maxLength={200} value={industry} onChange={e => setIndustry(e.target.value)} /></label></p>
      <p><label>Outcome {kind === "past_proposal" ? "(required; use unknown if unavailable)" : "(optional)"}<input required={kind === "past_proposal"} maxLength={1000} value={outcome} onChange={e => setOutcome(e.target.value)} /></label></p>
      <p><label><input type="checkbox" checked={synthetic} onChange={e => setSynthetic(e.target.checked)} /> This is synthetic demonstration material</label></p>
      <p><label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> I may use this material as evidence of my own work</label></p>
      <button className="primary" disabled={busy || !confirmed}>{busy ? "Indexing…" : "Index evidence"}</button>
    </form>
    <p role="status">{status}</p>{error && <p role="alert">{error}</p>}
    <p className="muted">Unknown dates and industries remain unknown. Reported outcomes are not independently verified. Text PDFs only; scanned PDFs need OCR. Re-upload the same filename and type to update its evidence.</p>
    <ul>{documents.map(d => <li key={d.document_id}>{d.filename} — {d.chunk_count} chunks, revision {d.revision}{" "}
      <button aria-label={`Remove ${d.filename}`} onClick={async () => { try { await request(`/documents/${d.document_id}`, "DELETE"); setHits([]); await reload(); } catch (e) { setError((e as Error).message); } }}>Remove</button></li>)}</ul>
    <form onSubmit={async e => { e.preventDefault(); try { setHits((await request<{ items: typeof hits }>(`/search?query=${encodeURIComponent(query)}&kind=${kind}`)).items); } catch (e) { setError((e as Error).message); } }}>
      <label>Search your evidence<input required minLength={2} value={query} onChange={e => setQuery(e.target.value)} /></label><button>Search evidence</button>
    </form>
    <ul>{hits.map(h => <li key={h.evidence_id}>{h.summary}<br /><span className="muted">{h.project} · {h.source}</span></li>)}</ul>
  </section>;
}
