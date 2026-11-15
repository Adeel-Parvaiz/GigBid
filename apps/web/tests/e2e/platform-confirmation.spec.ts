import { expect, test } from "@playwright/test";
import { register } from "./helpers";

test("Upwork confirmation requires separate review and an attachment choice", async ({ page }) => {
  await register(page);
  let confirmed = false;
  let calls = 0;
  await page.route("**/api/runs/platform-demo", route => route.fulfill({ json: {
    run_id: "platform-demo", kind: "bid", target: "fixture-job", status: confirmed ? "platform_confirmation_recorded" : "awaiting_platform_confirmation",
    trace_id: "fixture-trace", created_at: 0, summary: { submission: { platform_action_id: "fixture-action", review_hash: "a".repeat(64),
      platform_preview: { connects_cost: 8, connects_balance: 100, cover_letter: "A fixture proposal for UI testing." } } },
  } }));
  await page.route("**/api/runs/platform-demo/events?*", route => route.fulfill({ contentType: "text/event-stream",
    body: 'data: {"seq":1,"type":"done","status":"awaiting_platform_confirmation"}\n\n' }));
  await page.route("**/api/runs/platform-demo/platform-confirmation", async route => {
    const body = route.request().postDataJSON();
    expect(body.confirm_on_upwork).toBe(true);
    expect(body.attachments_choice).toBe("none");
    expect(body.review_hash).toBe("a".repeat(64));
    confirmed = true; calls++;
    await route.fulfill({ json: { status: "platform_confirmation_recorded", note: "Fixture only; no provider was contacted." } });
  });
  await page.goto("/runs/platform-demo");
  const confirm = page.getByRole("button", { name: "Confirm this action on Upwork", exact: true });
  await expect(confirm).toBeDisabled();
  await page.getByLabel(/I reviewed this action/).check();
  await expect(confirm).toBeDisabled();
  await page.getByLabel("Would you like to attach files or profile highlights?").selectOption("wanted");
  await expect(confirm).toBeDisabled();
  await page.getByLabel("Would you like to attach files or profile highlights?").selectOption("none");
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect(confirm).toBeHidden();
  expect(calls).toBe(1);
});
