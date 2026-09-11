/**
 * How the panel is built and tested.
 *
 * The dev server proxies /api to the running brawlfarm process instead of talking to it
 * across origins: the API has no CORS middleware on purpose, and a proxied request still
 * reaches it from 127.0.0.1, so the loopback-only guard is satisfied. The proxy carries
 * the SSE stream too, which is why changeOrigin stays off.
 */
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8765", changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    globals: false,
  },
});
