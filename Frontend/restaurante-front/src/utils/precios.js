export const formatearPrecioClp = (valor) =>
  new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(Number(valor || 0));

export const calcularPrecioOfertaVisual = (precio, porcentaje) => {
  const precioNumero = Number(precio);
  const porcentajeNumero = Number(porcentaje);
  if (!Number.isFinite(precioNumero) || !Number.isInteger(porcentajeNumero)) return null;
  if (precioNumero < 0 || porcentajeNumero < 1 || porcentajeNumero > 99) return null;
  return Math.round((precioNumero * (100 - porcentajeNumero)) / 100);
};

export const obtenerPrecioEfectivo = (item) =>
  Number(item?.precio_efectivo ?? item?.precio_oferta ?? item?.precio ?? 0);
