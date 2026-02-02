import path from "path";
import fs from "fs";
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import sirv from "sirv";

const staticDir = path.resolve(__dirname, "..", "static");

const staticPlugin = () => ({
  name: "cs2ze-static-assets",
  configureServer(server: { middlewares: { use: (path: string, fn: unknown) => void } }) {
    server.middlewares.use("/static", sirv(staticDir, { dev: true }));
  },
  closeBundle() {
    const outDir = path.resolve(__dirname, "dist", "static");
    if (!fs.existsSync(staticDir)) return;
    fs.mkdirSync(outDir, { recursive: true });
    fs.cpSync(staticDir, outDir, { recursive: true });
  }
});

export default defineConfig({
  plugins: [svelte(), staticPlugin()],
  publicDir: false,
  server: {
    strictPort: true,
    port: 5173,
    proxy: {
      "/__proxy": {
        target: "https://www.cs2ze.org",
        changeOrigin: true,
        rewrite: (pathValue) => pathValue.replace(/^\/__proxy/, "")
      }
    },
    fs: {
      allow: [path.resolve(__dirname, "..")]
    }
  },
  build: {
    target: "es2020"
  }
});
