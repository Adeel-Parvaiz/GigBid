import { expect, test } from "@playwright/test";
import { analyseUntilStudio, register } from "./helpers";

test("editing a draft saves it; a policy-violating edit blocks approval", async ({ page }) => {
  await register(page);
  await analyseUntilStudio(page);
  const box = page.getByLabel(/Edit the text/);

  await box.fill("Happy to scope this together here on the platform.");
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toBeDisabled();   // unsaved edit: save first
  await page.getByRole("button", { name: "Save edit" }).click();
  await page.getByRole("link", { name: /open studio/ }).click();            // re-checked by Compliance, back at the gate
  await expect(page.getByLabel(/Edit the text/)).toHaveValue("Happy to scope this together here on the platform.");

  await page.getByLabel(/Edit the text/).fill("Message me on WhatsApp for a quicker answer.");
  await page.getByRole("button", { name: "Save edit" }).click();
  await page.getByRole("link", { name: /open studio/ }).click();
  await expect(page.getByTestId("blocked")).toContainText("off_platform");
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toBeDisabled();
});
