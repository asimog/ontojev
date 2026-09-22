import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  use: {
    baseURL: process.env.CANCERJEV_WEB_URL ?? "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  reporter: "list",
});
