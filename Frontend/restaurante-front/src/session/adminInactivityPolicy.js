export const DEFAULT_INACTIVITY_MS = 15 * 60 * 1000;
export const DASHBOARD_INACTIVITY_MS = 2 * 60 * 60 * 1000;
export const DEFAULT_WARNING_MS = 60 * 1000;
export const DASHBOARD_WARNING_MS = 5 * 60 * 1000;

const DASHBOARD_ROUTE = /^\/dashboard\/[^/]+\/?$/;

export function getAdminRouteScope(pathname = "") {
  if (pathname.startsWith("/pedidos-cocina")) return null;
  if (DASHBOARD_ROUTE.test(pathname)) return "dashboard";
  if (
    pathname.startsWith("/dashboard/") ||
    pathname.startsWith("/carta-add/") ||
    pathname.startsWith("/carta-productos/") ||
    pathname === "/historial"
  ) {
    return "admin";
  }
  return null;
}

export function getInactivityPolicy(pathname = "") {
  const scope = getAdminRouteScope(pathname);
  if (!scope) return null;
  if (scope === "dashboard") {
    return {
      scope,
      timeoutMs: DASHBOARD_INACTIVITY_MS,
      warningMs: DASHBOARD_WARNING_MS,
    };
  }
  return {
    scope,
    timeoutMs: DEFAULT_INACTIVITY_MS,
    warningMs: DEFAULT_WARNING_MS,
  };
}

export function createActivityState(pathname, at = Date.now()) {
  const policy = getInactivityPolicy(pathname);
  return policy ? { ...policy, at } : null;
}

export function parseActivityState(rawValue) {
  if (!rawValue) return null;
  try {
    const state = JSON.parse(rawValue);
    if (
      Number.isFinite(Number(state?.at)) &&
      Number.isFinite(Number(state?.timeoutMs)) &&
      Number.isFinite(Number(state?.warningMs)) &&
      ["dashboard", "admin"].includes(state?.scope)
    ) {
      return {
        at: Number(state.at),
        timeoutMs: Number(state.timeoutMs),
        warningMs: Number(state.warningMs),
        scope: state.scope,
      };
    }
  } catch {
    return null;
  }
  return null;
}

export function getInactivityTiming(state, now = Date.now()) {
  if (!state) return null;
  const expiresAt = state.at + state.timeoutMs;
  const warningAt = expiresAt - state.warningMs;
  return {
    expiresAt,
    warningAt,
    remainingMs: Math.max(0, expiresAt - now),
    warningRemainingMs: Math.max(0, warningAt - now),
    isWarning: now >= warningAt && now < expiresAt,
    isExpired: now >= expiresAt,
  };
}
