import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

const apiPort = Number(process.env.GIGBID_E2E_API_PORT ?? "18000");
const webPort = Number(process.env.GIGBID_E2E_WEB_PORT ?? "13000");
const apiURL = `http://127.0.0.1:${apiPort}`;
const webURL = `http://127.0.0.1:${webPort}`;
const sampleData = fileURLToPath(new URL("../../data/sample", import.meta.url));

// Starts the real API (in-memory graph checkpointer, sample marketplace) and the web app. Run: npm run test:e2e
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [["html", { open: "never" }], ["list"], ["json", { outputFile: "test-results/results.json" }]],
  use: { baseURL: webURL, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
             { name: "phone", use: { viewport: { width: 390, height: 844 } }, grep: /@mobile/ }],
  webServer: [
    { command: `cd ../.. && python -m uvicorn apps.api.main:create_app --factory --port ${apiPort}`, url: `${apiURL}/health`, reuseExistingServer: false, timeout: 60_000,
      env: { REVIEWER_EMAIL: "reviewer@gigbid.test", REVIEWER_PASSWORD: "reviewer-pass-1", REVIEWER_PERSONA: "sample-ai-engineer",
        USERS_DB: ":memory:", RUNS_DB: ":memory:", DATABASE_URL: "", APP_SECRET_KEY: "e2e-secret", LLM_BACKEND: "heuristic",
        GIGBID_DATA_DIR: sampleData, PORTFOLIO_DIR: sampleData,
        GIGBID__marketplace__mode: "sample", GIGBID__portfolio__source: "local", GIGBID__workspace__source: "mcp", GIGBID__workspace__transport: "stdio" } },
    { command: `node scripts/run-vite.mjs --host 127.0.0.1 --port ${webPort} --strictPort`, url: webURL, reuseExistingServer: false,
      env: { GIGBID_DEV_API_URL: apiURL } },
  ],
});
