import { expect, test } from "@playwright/test";
import { register } from "./helpers";

test("marketplace down: banner, clear error state, and it recovers", async ({ page }) => {
  await register(page);
  await page.route("**/api/health", (r) => r.fulfill({ json: { api: "ok", marketplace: "degraded", queued_degraded_runs: 2 } }));
  await page.route("**/api/jobs", (r) => r.fulfill({ status: 503, json: { detail: "marketplace unavailable: marketplace_unavailable" } }));
  await page.reload();
  await expect(page.getByTestId("degraded-banner")).toContainText("Marketplace unavailable");
  await expect(page.getByTestId("degraded-banner")).toContainText("2 waiting");
  await expect(page.getByRole("alert").filter({ has: page.getByRole("button", { name: "Try again" }) })).toContainText("queued");

  await page.unroute("**/api/health");
  await page.unroute("**/api/jobs");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByTestId("job-card").first()).toBeVisible();
  await expect(page.getByTestId("degraded-banner")).toBeHidden({ timeout: 15_000 });   // health poll recovers
});
