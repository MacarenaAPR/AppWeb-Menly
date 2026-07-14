import {
  descartarLegacyRefreshToken,
  getAdminAccessToken,
  getLegacyRefreshToken,
  limpiarSesionAdminLocal,
  setAdminAccessToken,
  tieneSesionAdmin,
} from "./session/adminSession";

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

  const mensaje = data.message || data.mensaje || data.error || data.detail;
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
  } catch {
    console.error(endpoint, response.status, bodyText);
    throw new Error(fallbackMessage);
  }

  if (!response.ok) {
    console.error(endpoint, response.status, bodyText);
    const fallbackSeguro = mensajeSeguroPorEstado(response.status, fallbackMessage);
    const error = new Error(
      response.status >= 500 ? fallbackSeguro : extraerMensajeApi(data, fallbackSeguro)
    );
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  return data;
}

export function limpiarSesionYRedirigir(motivo = "") {
  limpiarSesionAdminLocal({ motivo });
  window.location.replace("/");
}

let refreshPromise = null;

const renovarAccessDesdeCookie = async () => {
  if (!tieneSesionAdmin()) return null;

  const ejecutar = async () => {
    const legacyRefresh = getLegacyRefreshToken();
    const response = await fetch(buildApiUrl("/token/refresh/"), {
      method: "POST",
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(legacyRefresh ? { "Content-Type": "application/json" } : {}),
      },
      ...(legacyRefresh ? { body: JSON.stringify({ refresh: legacyRefresh }) } : {}),
    });
    if (legacyRefresh) descartarLegacyRefreshToken();
    if (!response.ok) return null;

    const data = await response.json().catch(() => null);
    if (!data?.access) return null;
    setAdminAccessToken(data.access);
    return data.access;
  };

  if (navigator.locks?.request) {
    return navigator.locks.request("menly-admin-refresh", ejecutar);
  }
  return ejecutar();
};

const renovarAccessUnaVez = () => {
  if (!refreshPromise) {
    refreshPromise = renovarAccessDesdeCookie().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
};

export async function cerrarSesionAdmin({ motivo = "manual" } = {}) {
  try {
    await fetch(buildApiUrl("/logout/"), {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
  } catch {
    // El cierre local se completa aunque el backend no este disponible.
  } finally {
    limpiarSesionAdminLocal({ motivo });
    window.location.replace("/");
  }
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
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
    });

  let accessToken = getAdminAccessToken();
  if (!accessToken && tieneSesionAdmin()) {
    accessToken = await renovarAccessUnaVez();
    if (!accessToken) {
      limpiarSesionYRedirigir();
      return new Response(null, { status: 401 });
    }
  }

  let response = await hacerRequest(accessToken);

  if (response.status !== 401) {
    return response;
  }

  if (!tieneSesionAdmin()) {
    limpiarSesionYRedirigir();
    return response;
  }

  const renewedAccess = await renovarAccessUnaVez();
  if (!renewedAccess) {
    limpiarSesionYRedirigir();
    return response;
  }

  response = await hacerRequest(renewedAccess);
  return response;
}

export async function cocinaFetch(url, options = {}) {
  const finalUrl = buildApiUrl(url);
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    options.timeout || REQUEST_TIMEOUT_MS
  );

  try {
    return await fetch(finalUrl, {
      ...options,
      credentials: "include",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}
