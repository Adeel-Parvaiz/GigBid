// Browser evidence for the isolated, real-model GigSim workflow verifier.
const { chromium, expect } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await page.goto(process.env.EVIDENCE_WEB_URL + '/login');
    await page.getByLabel('Email').fill(process.env.EVIDENCE_EMAIL);
    await page.getByLabel('Password', { exact: true }).fill(process.env.EVIDENCE_PASSWORD);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Job inbox' })).toBeVisible();
    await page.goto(process.env.EVIDENCE_WEB_URL + process.env.EVIDENCE_PATH);
    if (process.env.EVIDENCE_APPROVE === '1') {
      await expect(page.getByRole('button', { name: 'Approve', exact: true })).toBeEnabled();
      await page.screenshot({ path: process.env.EVIDENCE_FILE, fullPage: true });
      await page.getByRole('button', { name: 'Approve', exact: true }).click();
      await expect(page.getByText('submitted', { exact: true }).first()).toBeVisible({ timeout: 60000 });
    } else {
      await page.waitForTimeout(700);
      await page.screenshot({ path: process.env.EVIDENCE_FILE, fullPage: true });
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
