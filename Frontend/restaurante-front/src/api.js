const trimTrailingSlash = (value = "") => String(value).replace(/\/+$/, "");
const trimLeadingSlash = (value = "") => String(value).replace(/^\/+/, "");

const getRequiredEnv = (name) => {
  const value = import.meta.env[name];

  if (!value) {
    throw new Error(`Falta configurar ${name} en el archivo .env`);
  }

  return value;
};

export const API = trimTrailingSlash(getRequiredEnv("VITE_API_URL"));
export const API_ORIGIN = API.replace(/\/api$/, "");
const REQUEST_TIMEOUT_MS = 10000;
export const MENSAJE_CUENTA_INACTIVA =
  "Tu cuenta está inactiva. Contacta al soporte de Menly.";

export const buildApiUrl = (path = "") => {
  if (!path) return API;
  if (/^https?:\/\//i.test(path)) return path;

  return `${API}/${trimLeadingSlash(path)}`;
};

export const buildMediaUrl = (path = "") => {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;

  return `${API_ORIGIN}/${trimLeadingSlash(path)}`;
};

export const buildMenuUrl = (slug) => {
  if (!slug) return "";

  const base = trimTrailingSlash(
    import.meta.env.VITE_PUBLIC_SITE_URL || window.location.origin
  );

  return `${base}/menu/${encodeURIComponent(slug)}`;
};

export function limpiarSesionYRedirigir() {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
  localStorage.removeItem("user");
  localStorage.removeItem("restaurante");
  window.location.href = "/";
}

export async function authFetch(url, options = {}) {
  const finalUrl = buildApiUrl(url);
  const method = (options.method || "GET").toUpperCase();
  const restaurante = JSON.parse(localStorage.getItem("restaurante") || "null");
  const withTimeout = async (requestUrl, requestOptions = {}) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(
      () => controller.abort(),
      requestOptions.timeout || REQUEST_TIMEOUT_MS
    );

    try {
      return await fetch(requestUrl, {
        ...requestOptions,
        signal: controller.signal,
      });
    } finally {
      window.clearTimeout(timeoutId);
    }
  };

  if (
    restaurante?.activo === false &&
    !["GET", "HEAD", "OPTIONS"].includes(method)
  ) {
    return new Response(
      JSON.stringify({ error: MENSAJE_CUENTA_INACTIVA }),
      {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  const hacerRequest = (accessToken) =>
    withTimeout(finalUrl, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
    });

  let response = await hacerRequest(localStorage.getItem("access"));

  if (response.status !== 401) {
    return response;
  }

  const refresh = localStorage.getItem("refresh");

  if (!refresh) {
    limpiarSesionYRedirigir();
    return response;
  }

  const refreshResponse = await withTimeout(buildApiUrl("/token/refresh/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh }),
  });

  if (!refreshResponse.ok) {
    limpiarSesionYRedirigir();
    return response;
  }

  const data = await refreshResponse.json();
  localStorage.setItem("access", data.access);

  response = await hacerRequest(data.access);
  return response;
}
