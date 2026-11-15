import { expect, test } from "@playwright/test";
import { register } from "./helpers";
import { mkdir } from "node:fs/promises";

test("portfolio upload is indexed, updated and searchable without restarting @mobile", async ({ page }) => {
  await register(page);
  await page.goto("/settings");
  const card = page.getByRole("region", { name: "Portfolio evidence" });
  await expect(card).toBeVisible();
  const bounds = await card.boundingBox();
  for (const input of await card.locator("input, select").all()) {
    const box = await input.boundingBox();
    if (box && bounds) expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width);
  }
  await card.getByLabel("Evidence file").setInputFiles({ name: "b1-browser.md", mimeType: "text/markdown", buffer: Buffer.from("# Synthetic fixture\nUniquebrowserB1 Celery workflow monitoring.") });
  await card.getByLabel("Evidence title", { exact: true }).fill("Synthetic browser fixture");
  await card.getByLabel("Project", { exact: true }).fill("B1 browser demo");
  await card.getByLabel("Skills (comma separated)").fill("Celery, Python");
  await card.getByLabel("This is synthetic demonstration material").check();
  await card.getByLabel("I may use this material as evidence of my own work").check();
  await card.getByRole("button", { name: "Index evidence", exact: true }).click();
  await expect(card.getByRole("status")).toContainText("Ready to search");
  await card.getByLabel("Search your evidence").fill("UniquebrowserB1 Celery");
  await card.getByRole("button", { name: "Search evidence", exact: true }).click();
  await expect(card.getByText(/UniquebrowserB1 Celery workflow monitoring/)).toBeVisible();
  await card.getByRole("button", { name: "Index evidence", exact: true }).click();
  await expect(card.getByRole("status")).toHaveText("Already indexed; no changes.");
  await card.getByLabel("Evidence file").setInputFiles({ name: "b1-browser.md", mimeType: "text/markdown", buffer: Buffer.from("# Synthetic fixture\nUpdatedbrowserB1 dbt lineage reporting.") });
  await card.getByRole("button", { name: "Index evidence", exact: true }).click();
  await expect(card.getByText(/revision 2/)).toBeVisible();
  await card.getByLabel("Search your evidence").fill("UpdatedbrowserB1 dbt");
  await card.getByRole("button", { name: "Search evidence", exact: true }).click();
  await expect(card.getByText(/UpdatedbrowserB1 dbt lineage reporting/)).toBeVisible();
  if (test.info().project.name === "desktop") {
    await mkdir("../../evals/results/b1", { recursive: true });
    await card.screenshot({ path: "../../evals/results/b1/portfolio-upload-search.png", style: "header.top { position: static !important; }" });
  }
  await card.getByRole("button", { name: "Remove b1-browser.md" }).click();
  await expect(card.getByRole("button", { name: "Remove b1-browser.md" })).toHaveCount(0);
});
