import { useCallback, useEffect, useRef, useState } from "react";
import { cerrarSesionAdmin } from "../api";
import {
  ADMIN_ACTIVITY_STATE_KEY,
  ADMIN_CHANNEL_NAME,
  ADMIN_LOGOUT_EVENT_KEY,
  limpiarSesionAdminLocal,
  tieneSesionAdmin,
} from "../session/adminSession";
import {
  createActivityState,
  getInactivityPolicy,
  getInactivityTiming,
  parseActivityState,
} from "../session/adminInactivityPolicy";

const ACTIVITY_THROTTLE_MS = 1500;
const ACTIVITY_EVENTS = [
  "mousemove",
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
  "click",
  "submit",
];

export default function useAdminInactivity(pathname) {
  const [warning, setWarning] = useState(null);
  const keepSessionRef = useRef(() => {});
  const closeSessionRef = useRef(() => {});

  useEffect(() => {
    const policy = getInactivityPolicy(pathname);
    if (!policy || !tieneSesionAdmin()) {
      return undefined;
    }

    let warningTimeoutId;
    let expirationTimeoutId;
    let countdownIntervalId;
    let lastEmission = 0;
    let scheduledActivityAt = 0;
    let closing = false;
    let channel = null;

    const clearTimers = () => {
      window.clearTimeout(warningTimeoutId);
      window.clearTimeout(expirationTimeoutId);
      window.clearInterval(countdownIntervalId);
    };

    const closeLocallyFromOtherTab = (reason = "") => {
      if (closing) return;
      closing = true;
      clearTimers();
      limpiarSesionAdminLocal({ motivo: reason, emitir: false });
      window.location.replace("/");
    };

    const closeForInactivity = async () => {
      if (closing) return;
      closing = true;
      clearTimers();
      await cerrarSesionAdmin({ motivo: "inactividad" });
    };

    const updateWarning = (activityState) => {
      const timing = getInactivityTiming(activityState);
      if (!timing || timing.isExpired) {
        closeForInactivity();
        return;
      }
      setWarning({
        scope: activityState.scope,
        remainingSeconds: Math.max(0, Math.ceil(timing.remainingMs / 1000)),
      });
    };

    const showWarning = (activityState) => {
      window.clearInterval(countdownIntervalId);
      updateWarning(activityState);
      countdownIntervalId = window.setInterval(() => {
        updateWarning(activityState);
      }, 1000);
    };

    const scheduleFromState = (activityState) => {
      if (Number(activityState?.at) <= scheduledActivityAt) return;
      scheduledActivityAt = Number(activityState.at);
      clearTimers();
      setWarning(null);
      const timing = getInactivityTiming(activityState);
      if (!timing) return;
      if (timing.isExpired) {
        closeForInactivity();
        return;
      }
      if (timing.isWarning) {
        showWarning(activityState);
      } else {
        warningTimeoutId = window.setTimeout(
          () => showWarning(activityState),
          timing.warningRemainingMs
        );
      }
      expirationTimeoutId = window.setTimeout(
        closeForInactivity,
        timing.remainingMs
      );
    };

    const publishActivity = ({ force = false } = {}) => {
      if (closing) return;
      const now = Date.now();
      if (!force && now - lastEmission < ACTIVITY_THROTTLE_MS) return;
      lastEmission = now;
      const activityState = createActivityState(pathname, now);
      if (!activityState) return;
      const serialized = JSON.stringify(activityState);
      localStorage.setItem(ADMIN_ACTIVITY_STATE_KEY, serialized);
      channel?.postMessage({ type: "activity", state: activityState });
      scheduleFromState(activityState);
    };

    keepSessionRef.current = () => publishActivity({ force: true });
    closeSessionRef.current = async () => {
      if (closing) return;
      closing = true;
      clearTimers();
      await cerrarSesionAdmin({ motivo: "manual" });
    };

    try {
      channel = new BroadcastChannel(ADMIN_CHANNEL_NAME);
      channel.onmessage = ({ data }) => {
        if (data?.type === "activity" && data.state) {
          scheduleFromState(data.state);
        }
        if (data?.type === "logout") {
          closeLocallyFromOtherTab(data.motivo);
        }
      };
    } catch {
      channel = null;
    }

    const onStorage = (event) => {
      if (event.key === ADMIN_ACTIVITY_STATE_KEY && event.newValue) {
        const activityState = parseActivityState(event.newValue);
        if (activityState) scheduleFromState(activityState);
      }
      if (event.key === ADMIN_LOGOUT_EVENT_KEY && event.newValue) {
        try {
          closeLocallyFromOtherTab(JSON.parse(event.newValue).motivo);
        } catch {
          closeLocallyFromOtherTab();
        }
      }
    };

    ACTIVITY_EVENTS.forEach((eventName) => {
      window.addEventListener(eventName, publishActivity, {
        passive: true,
        capture: eventName === "scroll" || eventName === "submit",
      });
    });
    window.addEventListener("storage", onStorage);

    // Entrar a cualquier sección es actividad real y descarta la política de
    // la ruta anterior. En el Dashboard inicia exactamente un nuevo plazo.
    publishActivity({ force: true });

    return () => {
      clearTimers();
      ACTIVITY_EVENTS.forEach((eventName) => {
        window.removeEventListener(eventName, publishActivity, {
          capture: eventName === "scroll" || eventName === "submit",
        });
      });
      window.removeEventListener("storage", onStorage);
      channel?.close();
      keepSessionRef.current = () => {};
      closeSessionRef.current = () => {};
    };
  }, [pathname]);

  const keepSession = useCallback(() => keepSessionRef.current(), []);
  const closeSession = useCallback(() => closeSessionRef.current(), []);

  const visibleWarning =
    getInactivityPolicy(pathname) && tieneSesionAdmin() ? warning : null;

  return { warning: visibleWarning, keepSession, closeSession };
}
