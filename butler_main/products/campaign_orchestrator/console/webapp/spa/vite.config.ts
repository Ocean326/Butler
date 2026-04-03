import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const rootDir = new URL(".", import.meta.url);

export default defineConfig({
  root: path.resolve(rootDir.pathname),
  base: "/console/",
  plugins: [react()],
  build: {
    outDir: path.resolve(rootDir.pathname, "..", "dist"),
    emptyOutDir: true
  },
  server: {
    host: "127.0.0.1",
    port: 4173
  }
});
