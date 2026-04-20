import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH ?? "/static/dashboard/",
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
          plotly: ["plotly.js-basic-dist-min", "react-plotly.js"],
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
