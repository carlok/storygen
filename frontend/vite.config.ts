import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      // "@/" maps to "src/" — works both locally and inside Docker containers
      "@": new URL("./src", import.meta.url).pathname,
    },
  },

  build: {
    // Output goes straight into the directory FastAPI serves as static files.
    outDir: "../web/static",
    emptyOutDir: true,
  },

  server: {
    // During `npm run dev` proxy API/auth calls to the running FastAPI container.
    proxy: {
      "/api":  { target: "http://localhost:8000", changeOrigin: true },
      "/auth": { target: "http://localhost:8000", changeOrigin: true },
    },
  },

  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    // Use the test-specific tsconfig so vitest globals (describe/vi/expect)
    // are typed correctly without polluting the production build tsconfig.
    typecheck: { tsconfig: "./tsconfig.test.json" },
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json"],
      reportsDirectory: "../coverage/frontend",
    },
  },
});
