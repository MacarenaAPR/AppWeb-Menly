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

  const normalizedSlug = encodeURIComponent(slug);
  return `https://${normalizedSlug}.menly.cl/#menu`;
};

const extraerMensajeApi = (data, fallbackMessage) => {
  if (!data) return fallbackMessage;
  if (typeof data === "string") return data;

  const mensaje = data.error || data.detail || data.message || data.mensaje;
  if (typeof mensaje === "string") return mensaje;

  const primerValor = Object.values(data).flat().find((valor) => typeof valor === "string");
  return primerValor || fallbackMessage;
};

const mensajeSeguroPorEstado = (status, fallbackMessage) => {
  if (status === 401) return "Tu sesion expiro. Inicia sesion nuevamente.";
  if (status === 403) return "No tienes permiso para realizar esta accion.";
  if (status >= 500) return "No pudimos procesar la solicitud. Intenta nuevamente.";
  return fallbackMessage;
};

export async function readJsonResponse(response, endpoint, fallbackMessage = "No se pudieron cargar los datos") {
  const contentType = response.headers.get("content-type") || "";
  const bodyText = await response.text();
  const isJson = contentType.includes("application/json");
  let data = null;

  if (!bodyText) {
    if (!response.ok) {
      console.error(endpoint, response.status);
      throw new Error(mensajeSeguroPorEstado(response.status, fallbackMessage));
    }

    return null;
  }

  if (!isJson) {
    console.error(endpoint, response.status, bodyText);
    throw new Error(mensajeSeguroPorEstado(response.status, fallbackMessage));
  }

  try {
    data = JSON.parse(bodyText);
  } catch (parseError) {
    console.error(endpoint, response.status, bodyText);
    throw new Error(fallbackMessage);
  }

  if (!response.ok) {
    console.error(endpoint, response.status, bodyText);
    const fallbackSeguro = mensajeSeguroPorEstado(response.status, fallbackMessage);
    throw new Error(response.status >= 500 ? fallbackSeguro : extraerMensajeApi(data, fallbackSeguro));
  }

  return data;
}

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

  let data = null;

  try {
    data = await readJsonResponse(
      refreshResponse,
      "/token/refresh/",
      "No se pudo renovar la sesion"
    );
  } catch {
    limpiarSesionYRedirigir();
    return response;
  }

  if (!data?.access) {
    limpiarSesionYRedirigir();
    return response;
  }

  localStorage.setItem("access", data.access);

  response = await hacerRequest(data.access);
  return response;
}
