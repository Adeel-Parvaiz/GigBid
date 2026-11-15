import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/a6", timeout: 120000, retries: 0,
  reporter: [["html", { outputFolder: "playwright-report-a6", open: "never" }], ["list"], ["json", { outputFile: "test-results/results.json" }]],
  use: { baseURL: "http://127.0.0.1:13040", viewport: { width: 1440, height: 1000 }, trace: "retain-on-failure" },
  webServer: [
    { command: "cd ../.. && python -m evals.runners.a6_fixture_api --port 18040", url: "http://127.0.0.1:18040/health", reuseExistingServer: false, timeout: 60000 },
    { command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 13040 --strictPort", url: "http://127.0.0.1:13040", reuseExistingServer: false,
      env: { GIGBID_DEV_API_URL: "http://127.0.0.1:18040" } },
  ],
});
