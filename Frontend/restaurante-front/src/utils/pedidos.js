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
export const ESTADO_CANCELADO = "cancelado";
export const ESTADOS_PEDIDO_ESPECIAL = [
  "pendiente",
  "confirmado",
  "en_preparacion",
  "listo",
  "entregado",
  "cancelado",
  "completado",
];
export const ESTADOS_PEDIDO_MANUAL = ["pendiente", "preparando", "listo", "en_reparto", "entregado", "cancelado"];

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

  if (Array.isArray(pedido?.transiciones_permitidas)) {
    return [
      pedido.estado,
      ...pedido.transiciones_permitidas.filter((estado) => estado !== pedido.estado),
    ];
  }

  const siguientePreparacion = tipoNormalizado === "manual" ? "preparando" : "en_preparacion";
  const transicionesFallback = {
    pendiente: [siguientePreparacion, "cancelado"],
    recibido: ["en_preparacion", "cancelado"],
    pendiente_confirmacion: ["en_preparacion", "cancelado"],
    confirmado: ["en_preparacion", "cancelado"],
    preparando: ["listo", "cancelado"],
    en_preparacion: ["listo", "cancelado"],
    listo: ["entregado", "cancelado"],
    en_reparto: ["entregado"],
    entregado: [],
    cancelado: [],
  };
  let permitidas = [...(transicionesFallback[pedido?.estado] || [])];
  const admiteReparto =
    pedido?.tipo_entrega === "delivery" &&
    (tipoNormalizado === "manual" || (tipoNormalizado === "whatsapp" && deliveryActivo));
  if (pedido?.estado === "listo" && admiteReparto) {
    permitidas = [ESTADO_EN_REPARTO, "cancelado"];
  }
  return pedido?.estado ? [pedido.estado, ...permitidas] : [];
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
    ["whatsapp", "manual", "especial"].includes(tipoNormalizado) &&
    Object.keys(datos).length === 1 &&
    Object.prototype.hasOwnProperty.call(datos, "estado");

  return esCambioSoloEstado ? `${endpoint}estado/` : endpoint;
};
