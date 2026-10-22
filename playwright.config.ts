import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PORT ?? 3100);

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 45_000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    // Demo data mode (no Supabase env) + a known preview secret
    command: `npm run start -- -p ${PORT}`,
    url: `http://localhost:${PORT}/api/places/suggest?q=`,
    reuseExistingServer: !process.env.CI,
    env: { PREVIEW_SECRET: "e2e-preview", ADMIN_PASSWORD: "e2e-admin", SUPABASE_URL: "", SUPABASE_SERVICE_ROLE_KEY: "" },
  },
});
