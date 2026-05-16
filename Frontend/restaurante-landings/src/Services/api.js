import { getSlugFromHostname } from "../utils/getSlugFromHostname";

export const BASE_URL = String(import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 9000;

export class ApiError extends Error {
  constructor(message, { status, payload } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const apiFetch = async (path, options = {}) => {
  if (!BASE_URL) {
    throw new ApiError("API no configurada");
  }

  if (window.location.protocol === "https:" && BASE_URL.startsWith("http://")) {
    throw new ApiError("La API debe usar HTTPS en produccion");
  }

  const url = /^https?:\/\//i.test(path) ? path : `${BASE_URL}/${String(path).replace(/^\/+/, "")}`;
  const retries = options.retries ?? 1;
  const timeout = options.timeout ?? REQUEST_TIMEOUT_MS;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          Accept: "application/json",
          ...(options.headers || {}),
        },
      });
      window.clearTimeout(timeoutId);

      const contentType = response.headers.get("content-type") || "";
      const payload = contentType.includes("application/json")
        ? await response.json()
        : await response.text();

      if (!response.ok) {
        throw new ApiError("Request failed", {
          status: response.status,
          payload,
        });
      }

      return payload;
    } catch (error) {
      window.clearTimeout(timeoutId);
      const canRetry =
        attempt < retries &&
        (error.name === "AbortError" || error.status >= 500 || !error.status);

      if (!canRetry) {
        throw error;
      }

      await delay(300 * (attempt + 1));
    }
  }
};

export const getMenu = async (slug = getSlugFromHostname()) => {
  if (!slug) {
    throw new Error("Slug de restaurante no disponible");
  }

  return apiFetch(`/menu/${slug}/`);
};
