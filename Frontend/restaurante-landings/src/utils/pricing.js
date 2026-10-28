const precioSeguro = (valor, respaldo = 0) => {
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero : respaldo;
};

export const obtenerPrecioOriginal = (item) => precioSeguro(item?.precio);

export const obtenerPrecioOferta = (item) => {
  if (item?.precio_oferta == null) return null;
  return precioSeguro(item.precio_oferta);
};

export const obtenerPrecioEfectivo = (item) => {
  const original = obtenerPrecioOriginal(item);
  return precioSeguro(
    item?.precio_efectivo ?? item?.precio_oferta ?? item?.precio,
    original,
  );
};

export const estaEnOferta = (producto) => {
  const porcentaje = Number(producto?.porcentaje_descuento);
  return Number.isInteger(porcentaje) && porcentaje >= 1 && porcentaje <= 99;
};

export const obtenerPreciosMinimos = (producto) => {
  const variantes = (producto?.variantes || []).filter((variante) => variante.activo !== false);
  if (!variantes.length) {
    return {
      original: obtenerPrecioOriginal(producto),
      efectivo: obtenerPrecioEfectivo(producto),
      tieneVariantes: false,
    };
  }
  return {
    original: Math.min(...variantes.map(obtenerPrecioOriginal)),
    efectivo: Math.min(...variantes.map(obtenerPrecioEfectivo)),
    tieneVariantes: true,
  };
};
