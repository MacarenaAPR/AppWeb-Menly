import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replaceAll("\\", "/");

          if (normalizedId.includes("/node_modules/react-router-dom/")) return "router";
          if (
            normalizedId.includes("/node_modules/react/") ||
            normalizedId.includes("/node_modules/react-dom/")
          ) {
            return "react";
          }
          if (
            normalizedId.includes("/node_modules/apexcharts/") ||
            normalizedId.includes("/node_modules/react-apexcharts/")
          ) {
            return "charts";
          }
          if (normalizedId.includes("/node_modules/jspdf/")) return "pdf";
          if (
            normalizedId.includes("/node_modules/axios/") ||
            normalizedId.includes("/node_modules/bootstrap/") ||
            normalizedId.includes("/node_modules/qrcode/")
          ) {
            return "vendor";
          }

          return undefined;
        },
      },
    },
  },
})
