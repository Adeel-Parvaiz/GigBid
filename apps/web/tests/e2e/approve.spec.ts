import { expect, test } from "@playwright/test";
import { analyseUntilStudio, register } from "./helpers";

test("inbox -> streamed run -> evidence on hover -> approve -> pipeline", async ({ page }) => {
  await register(page);
  await analyseUntilStudio(page);

  const claim = page.getByTestId("claim").nth(1);                            // first evidence-backed sentence
  await claim.hover();
  await expect(claim.getByRole("tooltip")).toContainText("evidence-");
  await page.mouse.move(0, 0);
  await claim.focus();                                                      // keyboard path; hover works the same
  await expect(claim.getByRole("tooltip")).toContainText("evidence-");
  await expect(page.getByTestId("dry-run")).toContainText("8 Connects");

  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("submitted").first()).toBeVisible();          // run viewer shows the final status

  await page.getByRole("link", { name: "Pipeline" }).click();
  await expect(page.getByRole("listitem", { name: "submitted" })).toContainText("job-001");
  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByTestId("connects")).toHaveText("8");
});

test("a pending approval survives a page refresh", async ({ page }) => {
  await register(page);
  await analyseUntilStudio(page);
  await page.reload();
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toBeEnabled();
});
