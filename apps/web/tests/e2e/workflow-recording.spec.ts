import { expect, test } from "@playwright/test";
import { analyseUntilStudio, register } from "./helpers";

test.use({ video: "on" });

test("record inbox to approved proposal to client reply", async ({ page }) => {
  test.setTimeout(180_000);
  const recordingStartedAt = Date.now();
  await register(page);
  await analyseUntilStudio(page);

  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("submitted").first()).toBeVisible();

  await page.getByRole("link", { name: "Messages" }).click();
  const conversation = page.locator("article.card").filter({ hasText: "conv-001" });
  await expect(conversation).toContainText("How would you handle the class imbalance");
  await conversation.getByRole("button", { name: "Draft a reply" }).click();
  await expect(page.getByTestId("timeline")).toContainText("draft_reply");
  await page.getByRole("link", { name: /open studio/ }).click();
  await expect(page.getByRole("heading", { name: "Reply studio" })).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByRole("region", { name: "Run progress" }).getByText("sent", { exact: true })).toBeVisible();
  await page.waitForTimeout(Math.max(0, 120_000 - (Date.now() - recordingStartedAt)));
});
