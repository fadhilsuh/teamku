import {defineConfig} from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  use: {baseURL: "http://127.0.0.1:3105"},
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3105",
    url: "http://127.0.0.1:3105/signup",
    reuseExistingServer: !process.env.CI,
  },
});
