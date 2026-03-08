import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./src/tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:3001",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "android-chrome-mobile",
      testMatch: /(^|[\\/])mobile-smoke\.spec\.ts$/,
      use: { ...devices["Pixel 7"] },
    },
    {
      name: "ios-webkit-mobile",
      testMatch: /(^|[\\/])mobile-smoke\.spec\.ts$/,
      use: { ...devices["iPhone 14"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    port: 3001,
    reuseExistingServer: true,
  },
});
