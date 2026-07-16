import { authFetch, readJsonResponse } from "./api";


const soportaWebPush = () => (
  "serviceWorker" in navigator
  && "PushManager" in window
  && "Notification" in window
);

const urlBase64AUint8Array = (base64Url) => {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4);
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  return Uint8Array.from(raw, (caracter) => caracter.charCodeAt(0));
};

export const registrarServiceWorkerMenly = async () => {
  if (!("serviceWorker" in navigator)) return null;
  return navigator.serviceWorker.register("/sw.js", { scope: "/" });
};

const obtenerRegistro = async () => {
  const registro = await registrarServiceWorkerMenly();
  if (!registro) throw new Error("Este navegador no es compatible con Service Worker.");
  return navigator.serviceWorker.ready;
};

const consultarEstadoBackend = async (endpoint) => {
  const response = await authFetch("/push/subscriptions/status/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint }),
  });
  return readJsonResponse(
    response,
    "/push/subscriptions/status/",
    "No se pudo consultar el estado de las notificaciones."
  );
};

export const obtenerEstadoWebPush = async () => {
  if (!soportaWebPush()) return { estado: "unsupported" };
  if (window.Notification.permission === "denied") return { estado: "denied" };

  const registro = await obtenerRegistro();
  const suscripcion = await registro.pushManager.getSubscription();
  if (!suscripcion) return { estado: "disabled" };

  const estadoBackend = await consultarEstadoBackend(suscripcion.endpoint);
  return { estado: estadoBackend.subscribed ? "enabled" : "disabled" };
};

export const activarWebPush = async () => {
  if (!soportaWebPush()) return { estado: "unsupported" };

  const permiso = await window.Notification.requestPermission();
  if (permiso !== "granted") {
    return { estado: permiso === "denied" ? "denied" : "disabled" };
  }

  const registro = await obtenerRegistro();
  let suscripcion = await registro.pushManager.getSubscription();
  let suscripcionCreada = false;

  if (!suscripcion) {
    const configResponse = await authFetch("/push/config/");
    const config = await readJsonResponse(
      configResponse,
      "/push/config/",
      "No se pudo cargar la configuracion Web Push."
    );
    if (!config?.configured || !config.vapid_public_key) {
      throw new Error("Web Push no esta configurado en el servidor.");
    }

    suscripcion = await registro.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64AUint8Array(config.vapid_public_key),
    });
    suscripcionCreada = true;
  }

  try {
    const response = await authFetch("/push/subscriptions/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...suscripcion.toJSON(),
        tipo_dispositivo: "panel",
      }),
    });
    await readJsonResponse(
      response,
      "/push/subscriptions/",
      "No se pudo registrar este equipo."
    );
  } catch (error) {
    if (suscripcionCreada) await suscripcion.unsubscribe().catch(() => false);
    throw error;
  }

  return { estado: "enabled" };
};

export const desactivarWebPush = async () => {
  if (!soportaWebPush()) return { estado: "unsupported" };

  const registro = await obtenerRegistro();
  const suscripcion = await registro.pushManager.getSubscription();
  if (!suscripcion) return { estado: "disabled" };

  const response = await authFetch("/push/subscriptions/", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint: suscripcion.endpoint }),
  });
  await readJsonResponse(
    response,
    "/push/subscriptions/",
    "No se pudo desactivar este equipo."
  );
  await suscripcion.unsubscribe();
  return { estado: "disabled" };
};
