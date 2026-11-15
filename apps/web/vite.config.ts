import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: /api -> FastAPI. Production: nginx does the same (infra/docker/nginx.conf).
export default defineConfig({
  plugins: [react()],
  optimizeDeps: { entries: ["index.html"] },
  server: { proxy: { "/api": { target: process.env.GIGBID_DEV_API_URL ?? "http://127.0.0.1:8000", rewrite: (p) => p.replace(/^\/api/, ""), changeOrigin: true } } },
});
