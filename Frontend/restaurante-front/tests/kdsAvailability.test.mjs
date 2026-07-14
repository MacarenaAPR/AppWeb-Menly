import test from "node:test";
import assert from "node:assert/strict";

import {
  KDS_ORDERS_POLLING_MS,
  KDS_STATUS_POLLING_MS,
  getKdsPollingConfig,
} from "../src/session/kdsAvailability.js";

test("el KDS abierto consulta comandas sin depender de actividad del usuario", () => {
  assert.deepEqual(getKdsPollingConfig({ open: true }), {
    target: "orders",
    intervalMs: KDS_ORDERS_POLLING_MS,
  });
});

test("el KDS cerrado detiene comandas y consulta solamente el estado del local", () => {
  assert.deepEqual(getKdsPollingConfig({ open: false }), {
    target: "status",
    intervalMs: KDS_STATUS_POLLING_MS,
  });
});

test("una sesión KDS invalidada detiene todo polling", () => {
  assert.equal(
    getKdsPollingConfig({ sessionInvalid: true, open: true }),
    null,
  );
});
