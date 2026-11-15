import { expect, test } from "@playwright/test";
import { register } from "./helpers";

test("onboarding: register, set rates, land on a ranked inbox", async ({ page }) => {
  await register(page);
  await expect(page.getByTestId("job-card")).toHaveCount(5);
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByLabel("Hourly rate (USD)")).toHaveValue("25");     // from onboarding
  await expect(page.getByLabel("Weekly Connects budget")).toHaveValue("40");
  await page.getByLabel("Hourly rate (USD)").fill("35");
  await page.getByLabel("Weekly Connects budget").fill("55");
  const saved = page.waitForResponse((response) => response.url().endsWith("/api/settings") && response.request().method() === "PUT" && response.ok());
  await page.getByRole("form", { name: "Rates, budgets and autonomy" }).getByRole("button", { name: "Save", exact: true }).click();
  await saved;
  await page.reload();
  await expect(page.getByLabel("Hourly rate (USD)")).toHaveValue("35");
  await expect(page.getByLabel("Weekly Connects budget")).toHaveValue("55");
});

test("unauthenticated visitors are sent to sign-in @mobile", async ({ page }) => {
  await page.goto("/inbox");
  await expect(page).toHaveURL(/\/login$/);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);                                             // no sideways scrolling on a phone
});
