import { defineConfig } from "vitest/config";
import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { TEST_DATABASE_URL } from "./test/db-url.js";

export const TEST_CLIENT_ID = "test-client.apps.googleusercontent.com";

export default defineConfig({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: "./wrangler.toml" },
      miniflare: {
        bindings: {
          GEMINI_API_KEY: "test-key",
          SESSION_SECRET: "test-session-secret",
          GOOGLE_CLIENT_ID: TEST_CLIENT_ID,
          USER_DAILY_LIMIT: "3"
        },
        hyperdrives: { HYPERDRIVE: TEST_DATABASE_URL }
      }
    })
  ],
  test: { include: ["test/**/*.test.js"], globalSetup: ["./test/global-setup.js"], fileParallelism: false }
});
