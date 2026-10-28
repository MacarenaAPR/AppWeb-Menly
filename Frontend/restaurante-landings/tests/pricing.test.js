import test from "node:test";
import assert from "node:assert/strict";
import {
  estaEnOferta,
  obtenerPrecioEfectivo,
  obtenerPreciosMinimos,
} from "../src/utils/pricing.js";

test("reconoce la oferta por un porcentaje valido aunque la bandera no venga tipada", () => {
  assert.equal(estaEnOferta({ porcentaje_descuento: 20 }), true);
  assert.equal(estaEnOferta({ en_oferta: "true", porcentaje_descuento: "20" }), true);
  assert.equal(estaEnOferta({ en_oferta: true, porcentaje_descuento: 0 }), false);
});

test("mantiene un precio normal visible si el precio efectivo falta o es invalido", () => {
  assert.equal(obtenerPrecioEfectivo({ precio: 10990 }), 10990);
  assert.equal(obtenerPrecioEfectivo({ precio: 10990, precio_efectivo: "invalido" }), 10990);
});

test("calcula los minimos original y efectivo de las variantes activas", () => {
  const precios = obtenerPreciosMinimos({
    variantes: [
      { precio: 12000, precio_efectivo: 9600, activo: true },
      { precio: 10000, precio_efectivo: 8000, activo: true },
      { precio: 5000, precio_efectivo: 4000, activo: false },
    ],
  });

  assert.deepEqual(precios, {
    original: 10000,
    efectivo: 8000,
    tieneVariantes: true,
  });
});
