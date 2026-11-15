import { expect, type Page } from "@playwright/test";

/** Every test registers its own user, so runs never leak between tests. */
export async function register(page: Page) {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/login");
  await page.getByRole("button", { name: "Create account" }).click();      // switch to register mode
  await expect(page.getByLabel("Persona")).toHaveValue(/.+/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("e2e-password-1");
  await page.getByRole("form", { name: "Create account" }).getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Job inbox" })).toBeVisible();
  return email;
}

/** Analyse job-001 and open the studio once the run reaches the approval gate. */
export async function analyseUntilStudio(page: Page, jobTitle = "Build a customer churn prediction baseline") {
  const card = page.getByTestId("job-card").filter({ hasText: jobTitle });
  await card.getByRole("button", { name: "Analyse" }).click();
  await expect(page.getByTestId("timeline")).toContainText("fit_matcher");
  await page.getByRole("link", { name: /open studio/ }).click();
  await expect(page.getByRole("heading", { name: /Proposal studio/ })).toBeVisible();
}
