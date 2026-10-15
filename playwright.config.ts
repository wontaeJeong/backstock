import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: "http://127.0.0.1:23001", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { browserName: "chromium", viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    { command: "uv run uvicorn apps.api.app:app --host 127.0.0.1 --port 29000", url: "http://127.0.0.1:29000/health/live", reuseExistingServer: false,
      env: { DATA_STORAGE_PATH: "var/e2e-data" } },
    { command: `pnpm --filter @backstock/web ${process.env.CI ? "start" : "dev"} --hostname 127.0.0.1 --port 23001`, url: "http://127.0.0.1:23001", reuseExistingServer: false,
      env: { API_INTERNAL_URL: "http://127.0.0.1:29000", NEXT_PUBLIC_DISABLE_REACT_DEVTOOLS: "1" }, timeout: 120_000 },
  ],
})
