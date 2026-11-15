import { expect, test } from "@playwright/test";
import { analyseUntilStudio, register } from "./helpers";

test("regenerate one evidence-backed paragraph without changing the others", async ({ page }) => {
  await register(page);
  await analyseUntilStudio(page);

  const editor = page.getByLabel("Edit the text, then “Save edit” (Compliance re-checks it)");
  const before = (await editor.inputValue()).split(/\n\s*\n/);
  const chooser = page.getByLabel("Paragraph");
  const button = page.getByRole("button", { name: "Regenerate paragraph", exact: true });

  await chooser.selectOption("1");
  await expect(button).toBeEnabled();
  const selected = Number(await chooser.inputValue());
  const response = page.waitForResponse((r) => r.url().includes("/regenerate-paragraph") && r.ok());
  await button.click();
  await response;

  const after = (await editor.inputValue()).split(/\n\s*\n/);
  expect(after).toHaveLength(before.length);
  expect(after[selected]).not.toBe(before[selected]);
  for (let i = 0; i < before.length; i++) {
    if (i !== selected) expect(after[i]).toBe(before[i]);
  }
  await expect(page.getByText("Save this edit before regenerating another paragraph.")).toBeVisible();
});
