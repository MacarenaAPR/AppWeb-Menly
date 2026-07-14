import test from "node:test";
import assert from "node:assert/strict";

import {
  DASHBOARD_INACTIVITY_MS,
  DASHBOARD_WARNING_MS,
  DEFAULT_INACTIVITY_MS,
  DEFAULT_WARNING_MS,
  createActivityState,
  getAdminRouteScope,
  getInactivityPolicy,
  getInactivityTiming,
  parseActivityState,
} from "../src/session/adminInactivityPolicy.js";

test("una sección administrativa expira a los 15 minutos y avisa un minuto antes", () => {
  const state = createActivityState("/carta-productos/koala-food", 1_000);
  assert.equal(state.timeoutMs, DEFAULT_INACTIVITY_MS);
  assert.equal(state.warningMs, DEFAULT_WARNING_MS);
  assert.equal(getInactivityTiming(state, 1_000 + DEFAULT_INACTIVITY_MS).isExpired, true);
});

test("el Dashboard expira a las dos horas y avisa cinco minutos antes", () => {
  const state = createActivityState("/dashboard/koala-food", 2_000);
  assert.equal(state.timeoutMs, DASHBOARD_INACTIVITY_MS);
  assert.equal(state.warningMs, DASHBOARD_WARNING_MS);
  assert.equal(getInactivityTiming(state, 2_000 + DASHBOARD_INACTIVITY_MS).isExpired, true);
});

test("entrar al Dashboard descarta el tiempo acumulado en la sección anterior", () => {
  const start = 10_000;
  const productsState = createActivityState("/carta-productos/koala-food", start);
  const dashboardEntry = start + 14 * 60 * 1000;
  const dashboardState = createActivityState("/dashboard/koala-food", dashboardEntry);

  assert.equal(getInactivityTiming(productsState, dashboardEntry).remainingMs, 60 * 1000);
  assert.equal(
    getInactivityTiming(dashboardState, dashboardEntry).remainingMs,
    DASHBOARD_INACTIVITY_MS,
  );
});

test("salir del Dashboard inicia un nuevo plazo administrativo de 15 minutos", () => {
  const start = 20_000;
  const ordersEntry = start + 60 * 60 * 1000;
  const ordersState = createActivityState("/dashboard/koala-food/pedidos", ordersEntry);
  assert.equal(getInactivityTiming(ordersState, ordersEntry).remainingMs, DEFAULT_INACTIVITY_MS);
});

test("una actividad nueva reinicia completamente la política de la ruta actual", () => {
  const first = createActivityState("/dashboard/koala-food/pedidos", 1_000);
  const second = createActivityState("/dashboard/koala-food/pedidos", 400_000);
  assert.ok(second.at > first.at);
  assert.equal(getInactivityTiming(second, second.at).remainingMs, DEFAULT_INACTIVITY_MS);
});

test("la advertencia aparece solo dentro de la ventana previa al cierre", () => {
  const adminState = createActivityState("/dashboard/koala-food/pedidos", 1_000);
  const warningStart = 1_000 + DEFAULT_INACTIVITY_MS - DEFAULT_WARNING_MS;
  assert.equal(getInactivityTiming(adminState, warningStart - 1).isWarning, false);
  assert.equal(getInactivityTiming(adminState, warningStart).isWarning, true);

  const dashboardState = createActivityState("/dashboard/koala-food", 2_000);
  const dashboardWarningStart =
    2_000 + DASHBOARD_INACTIVITY_MS - DASHBOARD_WARNING_MS;
  assert.equal(
    getInactivityTiming(dashboardState, dashboardWarningStart).isWarning,
    true,
  );
});

test("Mantener sesión equivale a registrar actividad nueva en la ruta actual", () => {
  const oldState = createActivityState("/dashboard/koala-food", 1_000);
  const keepAt = oldState.at + DASHBOARD_INACTIVITY_MS - 10_000;
  const renewedState = createActivityState("/dashboard/koala-food", keepAt);
  assert.equal(
    getInactivityTiming(renewedState, keepAt).remainingMs,
    DASHBOARD_INACTIVITY_MS,
  );
});

test("el paso del tiempo o polling sin actividad no modifica el estado", () => {
  const state = createActivityState("/dashboard/koala-food/pedidos", 50_000);
  const serializedBeforePolling = JSON.stringify(state);
  getInactivityTiming(state, state.at + 5 * 60 * 1000);
  getInactivityTiming(state, state.at + 10 * 60 * 1000);
  assert.equal(JSON.stringify(state), serializedBeforePolling);
});

test("KDS y las rutas públicas no tienen política de inactividad administrativa", () => {
  assert.equal(getAdminRouteScope("/pedidos-cocina"), null);
  assert.equal(getInactivityPolicy("/pedidos-cocina/activar/token"), null);
  assert.equal(getInactivityPolicy("/"), null);
});

test("el estado sincronizado conserva la política de la pestaña con última actividad", () => {
  const state = createActivityState("/dashboard/koala-food", 123_456);
  assert.deepEqual(parseActivityState(JSON.stringify(state)), state);
});
