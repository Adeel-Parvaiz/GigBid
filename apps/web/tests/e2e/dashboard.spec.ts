import { expect, test } from "@playwright/test";
import { register } from "./helpers";

test("overview uses live workspace data and fits a phone viewport @mobile", async ({ page }) => {
  await register(page);
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Workspace performance" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Marketplace status" })).toContainText(/ok|degraded/);
  await expect(page.getByRole("link", { name: "All jobs" })).toBeVisible();
  const horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(horizontalOverflow).toBe(false);
});
