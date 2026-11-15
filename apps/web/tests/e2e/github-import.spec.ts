import { expect, test } from "@playwright/test";
import { register } from "./helpers";

test("GitHub README import requires repository and authorship confirmation", async ({ page }) => {
  await register(page);
  let imported = false;
  await page.route("**/api/connections/github", route => route.fulfill({ json: {
    connected: true, status: "connected", login: "fixture-owner", read_only: true,
  } }));
  await page.route("**/api/connections/github/imports", async route => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      expect(body).toEqual({ owner: "fixture-owner", repo: "project", path: "README.md", authorship_confirmed: true });
      imported = true;
      await route.fulfill({ json: { evidence_id: "fixture-import" } });
    } else await route.fulfill({ json: { items: imported ? [{ evidence_id: "fixture-import" }] : [] } });
  });
  await page.goto("/settings");
  const card = page.getByRole("region", { name: "GitHub connection" });
  await expect(card.getByText("Connected as fixture-owner")).toBeVisible();
  const button = card.getByRole("button", { name: "Import README" });
  await expect(button).toBeDisabled();
  await card.getByLabel("Repository name").fill("project");
  await expect(button).toBeDisabled();
  await card.getByLabel(/I confirm this repository represents my own work/).check();
  await button.click();
  await expect(card.getByText("1 repository records saved for your account.")).toBeVisible();
});
