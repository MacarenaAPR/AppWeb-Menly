import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/react-router-dom")) return "router";
          if (id.includes("node_modules/react") || id.includes("node_modules/react-dom")) {
            return "react";
          }
          if (
            id.includes("node_modules/axios") ||
            id.includes("node_modules/bootstrap") ||
            id.includes("node_modules/qrcode")
          ) {
            return "vendor";
          }

          return undefined;
        },
      },
    },
  },
})
