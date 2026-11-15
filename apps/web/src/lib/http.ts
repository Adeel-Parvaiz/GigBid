import createClient from "openapi-fetch";
import { useCallback, useEffect, useState } from "react";
import type { paths } from "./api/schema";
import type { RunEvent } from "../types";

export const BASE = import.meta.env.VITE_API_URL ?? "/api";
export const tokenStore = {
  get: () => localStorage.getItem("gigbid_token"),
  set: (t: string) => localStorage.setItem("gigbid_token", t),
  clear: () => localStorage.removeItem("gigbid_token"),
};

export const api = createClient<paths>({ baseUrl: BASE });
api.use({
  onRequest({ request }) {
    const t = tokenStore.get();
    if (t) request.headers.set("Authorization", `Bearer ${t}`);
    return request;
  },
});

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function unwrap<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (!response.ok || data === undefined) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    if (response.status === 401) { tokenStore.clear(); }
    throw new ApiError(response.status, typeof detail === "string" ? detail : `HTTP ${response.status}`);
  }
  return data;
}

/** Loads data, exposes loading/error/empty-friendly state and a reload(). */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(() => {
    setLoading(true);
    fn().then((d) => { setData(d); setError(null); })
      .catch((e: ApiError) => setError(e))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(load, [load]);
  return { data, error, loading, reload: load };
}

/** SSE over fetch (EventSource cannot send the Authorization header). Ends at an approval gate or when the run is done. */
export async function* streamRun(runId: string, after: number, signal: AbortSignal): AsyncGenerator<RunEvent> {
  const res = await fetch(`${BASE}/runs/${runId}/events?after=${after}`, { headers: { Authorization: `Bearer ${tokenStore.get() ?? ""}` }, signal });
  if (!res.ok || !res.body) throw new ApiError(res.status, `stream failed (${res.status})`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (line) yield JSON.parse(line.slice(6)) as RunEvent;
    }
  }
}
