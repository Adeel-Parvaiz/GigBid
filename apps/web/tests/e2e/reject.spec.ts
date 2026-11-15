import { expect, test } from "@playwright/test";
import { analyseUntilStudio, register } from "./helpers";

test("reject requires a reason and records it in analytics", async ({ page }) => {
  await register(page);
  await analyseUntilStudio(page);
  const reject = page.getByRole("button", { name: "Reject", exact: true });
  await expect(reject).toBeDisabled();                                      // no reason yet
  await page.getByLabel("Reject reason").fill("opening is too generic");
  await reject.click();
  await expect(page.getByText("rejected").first()).toBeVisible();
  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByText("opening is too generic")).toBeVisible();
  await expect(page.getByText("n/a output tokens/sec")).toBeVisible();
  await expect(page.getByText(/Heuristic test backend; tokens are estimates/)).toBeVisible();
});
