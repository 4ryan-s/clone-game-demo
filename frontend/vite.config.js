import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const api = {
  "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
  "/c": { target: "http://127.0.0.1:8000", changeOrigin: true },
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: api },
  preview: { port: 4173, proxy: api },
});
