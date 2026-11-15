import { useEffect, useState } from "react";
import { api, unwrap, useLoad } from "../lib/http";

export function UpworkConnection() {
  const connection = useLoad(() => unwrap(api.GET("/connections/upwork")));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (connection.data?.status !== "awaiting_authorization") return;
    const timer = setInterval(connection.reload, 3000);
    return () => clearInterval(timer);
  }, [connection.data?.status, connection.reload]);

  async function connect() {
    setBusy(true); setError("");
    const popup = window.open("about:blank", "gigbid-upwork-oauth");
    try {
      const result = await unwrap(api.POST("/connections/upwork/authorize"));
      if (result.authorization_url) {
        if (popup) { popup.opener = null; popup.location.href = result.authorization_url; }
        else window.location.assign(result.authorization_url);
      } else { popup?.close(); if (result.status !== "connected") setError("Upwork could not start authorization. Try reconnecting."); }
      connection.reload();
    } catch (e) { popup?.close(); setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function switchMode(mode: string) {
    try { await unwrap(api.PUT("/connections/upwork/mode", { body: { mode } })); connection.reload(); }
    catch (e) { setError((e as Error).message); }
  }

  return <section className="card" aria-label="Upwork connection">
    <h2>Upwork connection</h2>
    <p>Authorize directly with Upwork. Your password stays with Upwork; connection tokens are encrypted on the server.</p>
    <p role="status">{connection.data?.connected ? "Upwork authorized" : "Upwork disconnected"} · Marketplace: {connection.data?.mode ?? "simulator"}</p>
    {connection.data?.status === "awaiting_authorization" && <p>Finish authorization in the Upwork window, then return here.</p>}
    <button disabled={busy} onClick={connect}>{busy ? "Connecting…" : connection.data?.connected ? "Reconnect Upwork" : "Connect Upwork"}</button>
    {connection.data?.connected && <>
      <button onClick={async () => { await api.DELETE("/connections/upwork"); connection.reload(); }}>Disconnect Upwork</button>
      {!connection.data.ready && <p>Connected. Live mode will become available after the discovered tool mappings have been verified.</p>}
      <button disabled={!connection.data.ready || connection.data.mode === "upwork"} onClick={() => switchMode("upwork")}>Use Upwork</button>
      <button disabled={!connection.data.reads_ready || connection.data.mode === "upwork_readonly"} onClick={() => switchMode("upwork_readonly")}>Use Upwork (read-only)</button>
      <button disabled={connection.data.mode === "simulator"} onClick={() => switchMode("simulator")}>Use simulator</button>
    </>}
    <p className="muted">Live proposals and replies require your approval here and a separate confirmation on Upwork. No live sends are automatic.</p>
    {(error || connection.error) && <p role="alert">{error || connection.error?.message}</p>}
  </section>;
}
