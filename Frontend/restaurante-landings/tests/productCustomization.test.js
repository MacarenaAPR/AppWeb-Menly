import test from "node:test";
import assert from "node:assert/strict";
import {
  calcularPrecioConfigurado,
  cambiarOpcionSeleccionada,
  construirResumenOpciones,
  crearClaveCarrito,
  obtenerIdsOpciones,
  obtenerTextoSeleccion,
  validarPersonalizacion,
} from "../src/utils/productCustomization.js";

const grupos = [
  {
    id: 3,
    nombre: "Proteínas",
    obligatorio: true,
    minimo_selecciones: 1,
    maximo_selecciones: 2,
    opciones: [
      { id: 12, nombre: "Carne", precio_adicional: 0, disponible: true },
      { id: 13, nombre: "Pollo", precio_adicional: 0, disponible: true },
      { id: 14, nombre: "Camarón", precio_adicional: 1000, disponible: true },
    ],
  },
  {
    id: 6,
    nombre: "Extras",
    obligatorio: false,
    minimo_selecciones: 0,
    maximo_selecciones: null,
    opciones: [
      { id: 25, nombre: "Queso extra", precio_adicional: 1500, disponible: true },
      { id: 26, nombre: "Agotado", precio_adicional: 500, disponible: false },
    ],
  },
];

test("genera textos de ayuda comprensibles", () => {
  assert.equal(obtenerTextoSeleccion({ minimo_selecciones: 1, maximo_selecciones: 1 }), "Elige 1");
  assert.equal(obtenerTextoSeleccion({ minimo_selecciones: 1, maximo_selecciones: 2 }), "Elige entre 1 y 2");
  assert.equal(obtenerTextoSeleccion({ minimo_selecciones: 0, maximo_selecciones: 2 }), "Elige hasta 2");
  assert.equal(obtenerTextoSeleccion({ minimo_selecciones: 0, maximo_selecciones: null }), "Opcional");
  assert.equal(obtenerTextoSeleccion({ minimo_selecciones: 2, maximo_selecciones: null }), "Elige al menos 2");
});

test("la selección única reemplaza la opción anterior", () => {
  const grupo = { id: 1, maximo_selecciones: 1 };
  const primera = cambiarOpcionSeleccionada({}, grupo, 10);
  const segunda = cambiarOpcionSeleccionada(primera, grupo, 11);
  assert.deepEqual(segunda, { "1": ["11"] });
});

test("la selección múltiple no supera el máximo", () => {
  const grupo = { id: 1, maximo_selecciones: 2 };
  let seleccion = cambiarOpcionSeleccionada({}, grupo, 10);
  seleccion = cambiarOpcionSeleccionada(seleccion, grupo, 11);
  seleccion = cambiarOpcionSeleccionada(seleccion, grupo, 12);
  assert.deepEqual(seleccion, { "1": ["10", "11"] });
});

test("valida mínimos obligatorios y omite opciones no disponibles", () => {
  assert.equal(validarPersonalizacion(grupos, {}).valida, false);
  assert.equal(validarPersonalizacion(grupos, { "3": ["12"] }).valida, true);
  assert.deepEqual(obtenerIdsOpciones(grupos, { "3": ["12"], "6": ["25", "26"] }), [12, 25]);
});

test("calcula precio, resumen histórico visual e identidad canónica", () => {
  const producto = { precio: 8990, grupos_opciones: grupos };
  const variante = { id: 42, precio: 9990 };
  const selecciones = { "3": ["13", "12"], "6": ["25"] };
  assert.equal(calcularPrecioConfigurado(producto, variante, selecciones), 11490);
  assert.equal(construirResumenOpciones(grupos, selecciones)[1].grupo_nombre, "Extras");
  assert.equal(crearClaveCarrito(10, 42, [25, 12, 13]), "10:42:12,13,25");
  assert.equal(
    crearClaveCarrito(10, 42, [25, 12, 13]),
    crearClaveCarrito(10, 42, [13, 25, 12]),
  );
  assert.notEqual(
    crearClaveCarrito(10, 42, [12, 13]),
    crearClaveCarrito(10, 42, [12, 13, 25]),
  );
});
