// Runs the SAME typed client and SSE reader the UI uses against a real API server (start it first, see npm run test:contract).
import { beforeAll, describe, expect, it } from "vitest";

const store = new Map<string, string>();
(globalThis as any).localStorage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), removeItem: (k: string) => void store.delete(k) };
const { api, streamRun, tokenStore, unwrap } = await import("../../src/lib/http");

describe("UI <-> API contract", () => {
  beforeAll(async () => {
    const t = await unwrap(api.POST("/auth/login", { body: { email: "reviewer@gigbid.test", password: "reviewer-pass-1" } }));
    tokenStore.set(t.token);
  });

  it("inbox -> streamed run -> approval gate -> approve -> submitted", async () => {
    const jobs = await unwrap(api.GET("/jobs"));
    expect(jobs.length).toBeGreaterThan(3);
    const run = await unwrap(api.POST("/jobs/{job_id}/runs", { params: { path: { job_id: "job-001" } } }));
    const evs = [];
    for await (const e of streamRun(run.run_id, 0, new AbortController().signal)) evs.push(e);
    const nodes = evs.filter((e) => e.type === "node").map((e) => e.node);
    expect(nodes).toEqual(expect.arrayContaining(["analyst", "risk", "fit_matcher", "decide", "pricing", "writer", "verifier", "critic", "compliance"]));
    const last = evs[evs.length - 1];
    expect(last.type).toBe("interrupt");
    expect((last.payload as any).allowed_actions).toContain("approve");

    const pending = await unwrap(api.GET("/approvals/pending"));
    expect(pending.map((p) => p.run.run_id)).toContain(run.run_id);   // what a refresh shows

    await unwrap(api.POST("/runs/{run_id}/approval", { params: { path: { run_id: run.run_id } }, body: { action: "approve" } }));
    const after = [];
    for await (const e of streamRun(run.run_id, last.seq, new AbortController().signal)) after.push(e);
    expect(after[after.length - 1]).toMatchObject({ type: "done", status: "submitted" });
    const detail = await unwrap(api.GET("/runs/{run_id}", { params: { path: { run_id: run.run_id } } }));
    expect(detail.status).toBe("submitted");
  });

  it("a blocked edit disables approve server-side (409) and errors carry a message", async () => {
    const run = await unwrap(api.POST("/jobs/{job_id}/runs", { params: { path: { job_id: "job-005" } } }));
    let last: any; for await (const e of streamRun(run.run_id, 0, new AbortController().signal)) last = e;
    await unwrap(api.POST("/runs/{run_id}/approval", { params: { path: { run_id: run.run_id } }, body: { action: "edit", edited_cover_letter: "Reach me on Telegram" } }));
    for await (const e of streamRun(run.run_id, last.seq, new AbortController().signal)) last = e;
    expect(last.payload.allowed_actions).toEqual(["edit", "reject"]);
    await expect(unwrap(api.POST("/runs/{run_id}/approval", { params: { path: { run_id: run.run_id } }, body: { action: "approve" } }))).rejects.toMatchObject({ status: 409 });
  });
});
