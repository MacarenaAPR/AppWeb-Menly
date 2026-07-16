export const PEDIDOS_POR_PAGINA = 10;

export const PAGINACION_INICIAL = Object.freeze({
  count: 0,
  next: null,
  previous: null,
  page: 1,
  totalPages: 1,
});

export const normalizarListaPedidos = (data) => {
  const lista = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
  const pedidosPorId = new Map();

  lista.forEach((pedido) => {
    if (pedido?.id !== undefined && pedido?.id !== null) {
      pedidosPorId.set(pedido.id, pedido);
    }
  });

  return Array.from(pedidosPorId.values());
};

export const normalizarPaginacionPedidos = (data, page) => {
  const count = Number(data?.count || 0);
  return {
    count,
    next: data?.next || null,
    previous: data?.previous || null,
    page,
    totalPages: Math.max(1, Math.ceil(count / PEDIDOS_POR_PAGINA)),
  };
};
