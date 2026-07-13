import { useEffect } from "react";
import { cerrarSesionAdmin } from "../api";
import {
  ADMIN_CHANNEL_NAME,
  ADMIN_LAST_ACTIVITY_KEY,
  ADMIN_LOGOUT_EVENT_KEY,
  esRutaPanelAdmin,
  limpiarSesionAdminLocal,
  tieneSesionAdmin,
} from "../session/adminSession";

export const ADMIN_INACTIVITY_MS = 10 * 60 * 1000;
const ACTIVITY_THROTTLE_MS = 1500;
const ACTIVITY_EVENTS = [
  "mousemove",
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
  "click",
];

export default function useAdminInactivity(pathname) {
  useEffect(() => {
    if (!esRutaPanelAdmin(pathname) || !tieneSesionAdmin()) return undefined;

    let timeoutId;
    let ultimaEmision = 0;
    let cerrando = false;
    let channel = null;

    const cerrarLocalDesdeOtraPestana = (motivo = "") => {
      if (cerrando) return;
      cerrando = true;
      limpiarSesionAdminLocal({ motivo, emitir: false });
      window.location.replace("/");
    };

    const programarCierre = () => {
      window.clearTimeout(timeoutId);
      const ultimaActividad = Number(
        localStorage.getItem(ADMIN_LAST_ACTIVITY_KEY) || Date.now()
      );
      const restante = Math.max(0, ADMIN_INACTIVITY_MS - (Date.now() - ultimaActividad));

      timeoutId = window.setTimeout(async () => {
        const actividadActual = Number(
          localStorage.getItem(ADMIN_LAST_ACTIVITY_KEY) || 0
        );
        if (Date.now() - actividadActual < ADMIN_INACTIVITY_MS) {
          programarCierre();
          return;
        }
        if (cerrando) return;
        cerrando = true;
        await cerrarSesionAdmin({ motivo: "inactividad" });
      }, restante);
    };

    const registrarActividad = () => {
      const ahora = Date.now();
      if (ahora - ultimaEmision < ACTIVITY_THROTTLE_MS) return;
      ultimaEmision = ahora;
      localStorage.setItem(ADMIN_LAST_ACTIVITY_KEY, String(ahora));
      channel?.postMessage({ type: "activity", at: ahora });
      programarCierre();
    };

    if (!localStorage.getItem(ADMIN_LAST_ACTIVITY_KEY)) {
      localStorage.setItem(ADMIN_LAST_ACTIVITY_KEY, String(Date.now()));
    }

    try {
      channel = new BroadcastChannel(ADMIN_CHANNEL_NAME);
      channel.onmessage = ({ data }) => {
        if (data?.type === "activity") programarCierre();
        if (data?.type === "logout") cerrarLocalDesdeOtraPestana(data.motivo);
      };
    } catch {
      channel = null;
    }

    const onStorage = (event) => {
      if (event.key === ADMIN_LAST_ACTIVITY_KEY) programarCierre();
      if (event.key === ADMIN_LOGOUT_EVENT_KEY && event.newValue) {
        try {
          cerrarLocalDesdeOtraPestana(JSON.parse(event.newValue).motivo);
        } catch {
          cerrarLocalDesdeOtraPestana();
        }
      }
    };

    ACTIVITY_EVENTS.forEach((eventName) => {
      window.addEventListener(eventName, registrarActividad, {
        passive: true,
        capture: eventName === "scroll",
      });
    });
    window.addEventListener("storage", onStorage);
    registrarActividad();

    return () => {
      window.clearTimeout(timeoutId);
      ACTIVITY_EVENTS.forEach((eventName) => {
        window.removeEventListener(eventName, registrarActividad, {
          capture: eventName === "scroll",
        });
      });
      window.removeEventListener("storage", onStorage);
      channel?.close();
    };
  }, [pathname]);
}
