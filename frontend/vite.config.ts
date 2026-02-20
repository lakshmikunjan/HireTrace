import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      // Only proxy /auth so the OAuth redirect link works from the frontend.
      // All JSON API calls go directly to http://localhost:8000 via axios baseURL.
      "/auth": "http://localhost:8000",
    },
  },
});
