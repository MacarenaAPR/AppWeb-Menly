export const ESTADOS_PEDIDO_BASE = [
  "recibido",
  "pendiente_confirmacion",
  "confirmado",
  "en_preparacion",
  "listo",
  "entregado",
  "cancelado",
];

export const ESTADO_EN_REPARTO = "en_reparto";
export const ESTADOS_PEDIDO_ESPECIAL = [
  "pendiente",
  "confirmado",
  "en_preparacion",
  "listo",
  "entregado",
  "cancelado",
  "completado",
];
export const ESTADOS_PEDIDO_MANUAL = ["pendiente", "preparando", "listo", "entregado", "cancelado"];

export const estadoLabels = {
  recibido: "Pedido recibido",
  pendiente_confirmacion: "Pendiente de confirmacion",
  pendiente: "Pendiente",
  confirmado: "Confirmado",
  en_preparacion: "En preparacion",
  preparando: "Preparando",
  en_reparto: "En reparto",
  listo: "Listo",
  entregado: "Entregado",
  cancelado: "Cancelado",
  completado: "Completado",
};

export const normalizarTipoPedido = (tipo) => (tipo === "menly" ? "manual" : tipo);

export const obtenerTipoPedidoDashboard = (pedido) =>
  normalizarTipoPedido(pedido?.tipo || pedido?.origen);

export const obtenerEstadosPedido = (tipo, pedido, { deliveryActivo = false } = {}) => {
  const tipoNormalizado = normalizarTipoPedido(tipo);

  if (tipoNormalizado === "manual") return ESTADOS_PEDIDO_MANUAL;
  if (tipoNormalizado === "especial") return ESTADOS_PEDIDO_ESPECIAL;
  if (tipoNormalizado !== "whatsapp") return [];
  if (!deliveryActivo || pedido?.tipo_entrega !== "delivery") return ESTADOS_PEDIDO_BASE;

  const estados = [...ESTADOS_PEDIDO_BASE];
  const indiceListo = estados.indexOf("listo");
  estados.splice(indiceListo >= 0 ? indiceListo + 1 : estados.length, 0, ESTADO_EN_REPARTO);
  return estados;
};

export const obtenerEndpointDetallePedido = (tipo, id) => {
  const tipoNormalizado = normalizarTipoPedido(tipo);
  if (tipoNormalizado === "whatsapp") return `/mi-restaurante/pedidos/whatsapp/${id}/`;
  if (tipoNormalizado === "manual") return `/mi-restaurante/pedidos/manuales/${id}/`;
  if (tipoNormalizado === "especial") return `/mi-restaurante/pedidos/especiales/${id}/`;
  return "";
};

export const obtenerEndpointActualizacionPedido = (tipo, id, datos = {}) => {
  const tipoNormalizado = normalizarTipoPedido(tipo);
  const endpoint = obtenerEndpointDetallePedido(tipoNormalizado, id);
  const esCambioSoloEstado =
    tipoNormalizado === "whatsapp" &&
    Object.keys(datos).length === 1 &&
    Object.prototype.hasOwnProperty.call(datos, "estado");

  return esCambioSoloEstado ? `${endpoint}estado/` : endpoint;
};
