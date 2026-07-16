import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizarListaPedidos,
  normalizarPaginacionPedidos,
} from "../src/utils/paginacionPedidos.js";


test("normaliza la metadata de 25 pedidos en tres paginas", () => {
  const paginacion = normalizarPaginacionPedidos(
    { count: 25, next: "?page=3", previous: "?page=1" },
    2,
  );

  assert.deepEqual(paginacion, {
    count: 25,
    next: "?page=3",
    previous: "?page=1",
    page: 2,
    totalPages: 3,
  });
});

test("un refresco de polling no deja IDs duplicados en la pagina visible", () => {
  const pedidos = normalizarListaPedidos({
    results: [
      { id: 3, numero_pedido: 3 },
      { id: 2, numero_pedido: 2 },
      { id: 2, numero_pedido: 2 },
      { id: 1, numero_pedido: 1 },
    ],
  });

  assert.deepEqual(pedidos.map((pedido) => pedido.id), [3, 2, 1]);
});
