import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

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
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json"],
      reportsDirectory: "../coverage/frontend",
    },
  },
});
