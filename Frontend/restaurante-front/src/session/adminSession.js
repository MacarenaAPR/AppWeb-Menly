export const ADMIN_SESSION_KEY = "menly.admin.session";
export const ADMIN_LAST_ACTIVITY_KEY = "menly.admin.lastActivity";
export const ADMIN_LOGOUT_EVENT_KEY = "menly.admin.logoutEvent";
export const ADMIN_CHANNEL_NAME = "menly-admin-session";
export const ADMIN_LOGOUT_MESSAGE_KEY = "menly.admin.logoutMessage";

let accessToken = localStorage.getItem("access") || null;
let legacyRefreshToken = localStorage.getItem("refresh") || null;

try {
  const restauranteAnterior = JSON.parse(
    localStorage.getItem("restaurante") || "null"
  );
  if (
    accessToken &&
    legacyRefreshToken &&
    ["dueno", "admin", "empleado"].includes(restauranteAnterior?.rol)
  ) {
    localStorage.setItem(ADMIN_SESSION_KEY, "ADMIN");
    if (!localStorage.getItem(ADMIN_LAST_ACTIVITY_KEY)) {
      localStorage.setItem(ADMIN_LAST_ACTIVITY_KEY, String(Date.now()));
    }
  }
} catch {
  accessToken = null;
  legacyRefreshToken = null;
}

// Limpieza unica de credenciales de versiones anteriores. Los JWT nuevos solo
// viven en memoria (access) y en cookie HttpOnly (refresh).
localStorage.removeItem("access");
localStorage.removeItem("refresh");

export function setAdminAccessToken(token) {
  accessToken = token || null;
}

export function getAdminAccessToken() {
  return accessToken;
}

export function getLegacyRefreshToken() {
  return legacyRefreshToken;
}

export function descartarLegacyRefreshToken() {
  legacyRefreshToken = null;
}

export function iniciarSesionAdmin(data) {
  setAdminAccessToken(data.access);
  localStorage.setItem("user", JSON.stringify(data.user));
  localStorage.setItem("restaurante", JSON.stringify(data.restaurante));
  localStorage.setItem(ADMIN_SESSION_KEY, "ADMIN");
  localStorage.setItem(ADMIN_LAST_ACTIVITY_KEY, String(Date.now()));
}

export function tieneSesionAdmin() {
  if (localStorage.getItem(ADMIN_SESSION_KEY) !== "ADMIN") return false;

  try {
    const restaurante = JSON.parse(localStorage.getItem("restaurante") || "null");
    return ["dueno", "admin", "empleado"].includes(restaurante?.rol);
  } catch {
    return false;
  }
}

export function limpiarSesionAdminLocal({ motivo = "", emitir = true } = {}) {
  setAdminAccessToken(null);
  legacyRefreshToken = null;
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
  localStorage.removeItem("user");
  localStorage.removeItem("restaurante");
  localStorage.removeItem(ADMIN_SESSION_KEY);
  localStorage.removeItem(ADMIN_LAST_ACTIVITY_KEY);

  if (motivo === "inactividad") {
    sessionStorage.setItem(
      ADMIN_LOGOUT_MESSAGE_KEY,
      "Tu sesiÃ³n se cerrÃ³ por inactividad."
    );
  }

  if (emitir) {
    const payload = JSON.stringify({ motivo, at: Date.now() });
    localStorage.setItem(ADMIN_LOGOUT_EVENT_KEY, payload);
    try {
      const channel = new BroadcastChannel(ADMIN_CHANNEL_NAME);
      channel.postMessage({ type: "logout", motivo });
      channel.close();
    } catch {
      // El evento storage mantiene compatibilidad si BroadcastChannel no existe.
    }
  }
}

export function consumirMensajeCierreAdmin() {
  const mensaje = sessionStorage.getItem(ADMIN_LOGOUT_MESSAGE_KEY) || "";
  sessionStorage.removeItem(ADMIN_LOGOUT_MESSAGE_KEY);
  return mensaje;
}

export function esRutaPanelAdmin(pathname = "") {
  return (
    pathname.startsWith("/dashboard/") ||
    pathname.startsWith("/carta-add/") ||
    pathname.startsWith("/carta-productos/") ||
    pathname === "/historial"
  );
}
