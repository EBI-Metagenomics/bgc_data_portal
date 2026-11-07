import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  // Relative base: chunk / asset URLs resolve against the entry's own URL
  // (``import.meta.url``), so the same bundle works at ``/static/dashboard/``
  // and behind an ingress prefix (``/finn-srv/mgnify-bgcs/static/dashboard/``)
  // without a build-time VITE_BASE_PATH. API / router paths are unaffected —
  // they read ``<meta name="base-path">`` at runtime.
  base: "./",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../static/dashboard",
    emptyOutDir: true,
    chunkSizeWarningLimit: 5000,
    rollupOptions: {
      output: {
        entryFileNames: "assets/index.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name].[ext]",
        manualChunks: {
          // The one Plotly build (see src/lib/plotly.ts). Only the factory
          // entry of react-plotly.js is listed: its default entry would pull
          // the full ``plotly.js`` source package in as a second copy.
          plotly: ["plotly.js-dist-min", "react-plotly.js/factory"],
          vendor: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
