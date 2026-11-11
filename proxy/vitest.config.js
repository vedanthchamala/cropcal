import { defineConfig } from "vitest/config";
import { cloudflareTest } from "@cloudflare/vitest-plugin";

export default defineConfig({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: "./wrangler.toml" },
      miniflare: { bindings: { GEMINI_API_KEY: "test-key" } }
    })
  ],
  test: { include: ["test/**/*.test.js"] }
});
