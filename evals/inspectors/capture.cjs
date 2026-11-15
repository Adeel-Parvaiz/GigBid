// Capture the official Inspector UI against the isolated A7 fixture catalog.
// Run with INSPECTOR_URL and PLAYWRIGHT_BROWSERS_PATH; never use live accounts.
const path = require('path');
const fs = require('fs');
const { chromium } = require('../../apps/web/node_modules/@playwright/test');

(async () => {
  const out = path.resolve(__dirname, '../results/inspector');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const observations = [];
  try {
    for (const [server, tool, expected, file] of [
      ['Portfolio', 'list_skills', 'scikit-learn', '01-portfolio.png'],
      ['Marketplace', 'get_connects_balance', 'connects', '02-marketplace.png'],
      ['Workspace', 'get_free_slots', 'slots', '03-workspace.png'],
    ]) {
      const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
      await page.goto(process.env.INSPECTOR_URL || 'http://127.0.0.1:16274');
      await page.locator(`input[aria-label*="GigBid ${server}"]`).check({ force: true });
      await page.getByText('Tools', { exact: true }).click();
      await page.getByRole('button', { name: tool, exact: true }).click();
      if (server === 'Workspace') {
        await page.getByRole('textbox', { name: 'Start Date', exact: true }).fill('2026-11-16');
      }
      await page.getByRole('button', { name: 'Execute Tool', exact: true }).click();
      await page.getByText('Run #1', { exact: true }).waitFor();
      await page.getByText('Structured Output', { exact: true }).waitFor();
      const text = await page.locator('body').innerText();
      if (!text.includes(expected) || !text.includes('TOOLS/CALL') || !text.includes('OK')) {
        throw new Error(`${server}: successful structured tool response missing`);
      }
      await page.screenshot({ path: path.join(out, file), fullPage: true });
      fs.writeFileSync(path.join(out, `${server.toLowerCase()}.txt`), text);
      observations.push({ server, tool, structuredOutput: true, screenshot: file });
      await page.close();
    }
    fs.writeFileSync(path.join(out, 'observations.json'), JSON.stringify({
      capturedAt: new Date().toISOString(), inspector: '@modelcontextprotocol/inspector@2.15.0',
      environment: 'isolated sample fixtures; no live accounts or writes', observations,
    }, null, 2));
    console.log(JSON.stringify(observations));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
