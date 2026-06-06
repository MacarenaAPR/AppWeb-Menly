
// https://vite.dev/config/
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const parseAllowedHosts = (value) =>
  String(value || "")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const allowedHosts = parseAllowedHosts(env.VITE_DEV_ALLOWED_HOSTS);

  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules/react-router-dom")) return "router";
            if (id.includes("node_modules/react") || id.includes("node_modules/react-dom")) {
              return "react";
            }

            return undefined;
          },
        },
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      allowedHosts: allowedHosts.length
        ? allowedHosts
        : [".localhost", ".menly.localhost", ".lvh.me", ".nip.io"],
    },
  };
});
