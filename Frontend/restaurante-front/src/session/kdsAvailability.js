export const KDS_ORDERS_POLLING_MS = 10_000;
export const KDS_STATUS_POLLING_MS = 10_000;

export function getKdsPollingConfig({ sessionInvalid = false, open = null } = {}) {
  if (sessionInvalid) return null;
  if (open === false) {
    return { target: "status", intervalMs: KDS_STATUS_POLLING_MS };
  }
  return { target: "orders", intervalMs: KDS_ORDERS_POLLING_MS };
}
