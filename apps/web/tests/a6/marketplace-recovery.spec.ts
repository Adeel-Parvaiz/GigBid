import { expect, test } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { register } from "../e2e/helpers";

test("real marketplace kill queues work, recovers automatically and still requires approval", async ({ page, request }) => {
  const evidence = resolve(process.cwd(), "../../evals/results/a6");
  await mkdir(evidence, { recursive: true });
  const login = await request.post("http://127.0.0.1:18040/auth/login", { data: { email: "reviewer@gigbid.test", password: "reviewer-pass-1" } });
  const admin = { Authorization: `Bearer ${(await login.json()).token}` };
  const metrics = async () => (await request.get("http://127.0.0.1:18040/_testing/state", { headers: admin })).json();
  await register(page);
  const user = { Authorization: `Bearer ${await page.evaluate(() => localStorage.getItem("gigbid_token"))}` };
  const initial = await metrics();
  await expect(page.getByTestId("job-card")).toHaveCount(5);
  await request.post("http://127.0.0.1:18040/_testing/marketplace/kill", { headers: admin });
  await page.reload();
  await expect(page.getByTestId("degraded-banner")).toContainText("Marketplace unavailable", { timeout: 20000 });
  await expect(page.getByRole("alert").filter({ has: page.getByRole("button", { name: "Try again" }) })).toBeVisible();
  const start = await request.post("http://127.0.0.1:18040/jobs/job-001/runs", { headers: user });
  const queuedId = (await start.json()).run_id;
  await expect.poll(async () => (await request.get(`http://127.0.0.1:18040/runs/${queuedId}`, { headers: user })).json().then(r => r.status), { timeout: 20000 }).toBe("queued_degraded");
  await expect(page.getByTestId("degraded-banner")).toContainText("1 waiting", { timeout: 20000 });
  await page.screenshot({ path: resolve(evidence, "01-marketplace-down-queued.png"), fullPage: true });
  const down = await metrics();
  expect(down.balance).toBe(100); expect(down.submissions).toBe(0);
  await request.post("http://127.0.0.1:18040/_testing/marketplace/start", { headers: admin });
  let recoveredId = "";
  await expect.poll(async () => {
    const runs = await (await request.get("http://127.0.0.1:18040/runs", { headers: user })).json();
    const run = runs.find((r: { run_id: string; status: string }) => r.run_id !== queuedId && r.status === "awaiting_approval");
    recoveredId = run?.run_id ?? ""; return Boolean(run);
  }, { timeout: 60000 }).toBe(true);
  await expect(page.getByTestId("degraded-banner")).toBeHidden({ timeout: 20000 });
  await expect(page.getByTestId("job-card")).toHaveCount(5); // recovered without clicking Try again
  const recovered = await metrics();
  expect(recovered.marketplace_pid).not.toBe(initial.marketplace_pid);
  expect(recovered.balance).toBe(100); expect(recovered.submissions).toBe(0);
  await page.goto(`/studio/${recoveredId}`);
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toBeEnabled();
  await page.screenshot({ path: resolve(evidence, "02-recovered-awaiting-approval.png"), fullPage: true });
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("submitted", { exact: true }).first()).toBeVisible();
  const final = await metrics();
  expect(final.balance).toBe(92); expect(final.submissions).toBe(1);
  await writeFile(resolve(evidence, "observations.json"), JSON.stringify({ scope: "Real process kill/restart, API recovery loop, Chromium; HeuristicLLM and synthetic marketplace only", initial, down, recovered, final,
    automatic_recovery: true, approval_required_after_recovery: true, no_spend_before_approval: true }, null, 2));
});
