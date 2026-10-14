import test from "node:test";
import assert from "node:assert/strict";
import {
  calcularAdicionalOpciones,
  crearClaveLineaPedido,
  obtenerIdsOpcionesCatalogo,
  obtenerIdsOpcionesSnapshot,
  validarSelecciones,
} from "../src/utils/pedidoPersonalizacion.js";

const grupos = [{
  id: 1,
  nombre: "Extras",
  obligatorio: true,
  minimo_selecciones: 1,
  maximo_selecciones: 2,
  opciones: [
    { id: 12, nombre: "Queso", precio_adicional: 1500, disponible: true },
    { id: 13, nombre: "Palta", precio_adicional: 500, disponible: true },
    { id: 14, nombre: "Agotada", precio_adicional: 900, disponible: false },
  ],
}];

test("canoniza la identidad por producto, variante y opciones", () => {
  assert.equal(crearClaveLineaPedido(10, 42, [13, 12]), "10:42:12,13");
  assert.notEqual(
    crearClaveLineaPedido(10, 42, [12]),
    crearClaveLineaPedido(10, 42, [13]),
  );
});

test("valida minimos y excluye opciones no disponibles", () => {
  assert.deepEqual(validarSelecciones(grupos, {}), { 1: "Selecciona al menos 1 opcion(es)." });
  assert.deepEqual(validarSelecciones(grupos, { 1: ["14"] }), { 1: "Selecciona al menos 1 opcion(es)." });
  assert.deepEqual(validarSelecciones(grupos, { 1: ["12"] }), {});
});

test("calcula adicionales y payload solo con ids disponibles", () => {
  const selecciones = { 1: ["13", "12", "14"] };
  assert.deepEqual(obtenerIdsOpcionesCatalogo(grupos, selecciones), [12, 13]);
  assert.equal(calcularAdicionalOpciones(grupos, selecciones), 2000);
});

test("lee ids desde snapshots manuales o WhatsApp", () => {
  const snapshot = [{
    grupo_id: 1,
    grupo_nombre: "Extras",
    opciones: [{ opcion_id: 25, nombre: "Queso extra" }, { opcion_id: 12, nombre: "Palta" }],
  }];
  assert.deepEqual(obtenerIdsOpcionesSnapshot({ grupos_opciones: snapshot }), [12, 25]);
  assert.deepEqual(obtenerIdsOpcionesSnapshot({ opciones_snapshot: snapshot }), [12, 25]);
  assert.deepEqual(obtenerIdsOpcionesSnapshot({}), []);
});
