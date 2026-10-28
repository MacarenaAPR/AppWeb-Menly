import { obtenerPrecioEfectivo, obtenerPrecioOriginal } from "./pricing.js";

const comoId = (valor) => String(valor);

export const gruposPersonalizacion = (producto) => producto?.grupos_opciones || [];

export const obtenerTextoSeleccion = (grupo) => {
  const minimo = Math.max(0, Number(grupo?.minimo_selecciones) || 0);
  const maximo = grupo?.maximo_selecciones === null
    ? null
    : Math.max(0, Number(grupo?.maximo_selecciones) || 0);

  if (minimo === 1 && maximo === 1) return "Elige 1";
  if (minimo > 0 && maximo !== null && minimo !== maximo) {
    return `Elige entre ${minimo} y ${maximo}`;
  }
  if (minimo > 0 && maximo === minimo) return `Elige ${minimo}`;
  if (minimo === 0 && maximo !== null) return `Elige hasta ${maximo}`;
  if (minimo > 0 && maximo === null) return `Elige al menos ${minimo}`;
  return "Opcional";
};

export const obtenerSeleccionGrupo = (selecciones, grupoId) =>
  (selecciones?.[comoId(grupoId)] || []).map(comoId);

export const cambiarOpcionSeleccionada = (selecciones, grupo, opcionId) => {
  const grupoId = comoId(grupo.id);
  const opcionNormalizada = comoId(opcionId);
  const actuales = obtenerSeleccionGrupo(selecciones, grupo.id);
  const yaSeleccionada = actuales.includes(opcionNormalizada);
  const maximo = grupo.maximo_selecciones === null
    ? null
    : Number(grupo.maximo_selecciones);

  let siguientes;
  if (maximo === 1) {
    siguientes = [opcionNormalizada];
  } else if (yaSeleccionada) {
    siguientes = actuales.filter((id) => id !== opcionNormalizada);
  } else if (maximo !== null && actuales.length >= maximo) {
    siguientes = actuales;
  } else {
    siguientes = [...actuales, opcionNormalizada];
  }

  return { ...(selecciones || {}), [grupoId]: siguientes };
};

export const validarPersonalizacion = (grupos = [], selecciones = {}) => {
  const errores = {};

  grupos.forEach((grupo) => {
    const disponibles = new Set(
      (grupo.opciones || [])
        .filter((opcion) => opcion.disponible !== false)
        .map((opcion) => comoId(opcion.id)),
    );
    const cantidad = obtenerSeleccionGrupo(selecciones, grupo.id)
      .filter((id) => disponibles.has(id)).length;
    const minimoConfigurado = Math.max(0, Number(grupo.minimo_selecciones) || 0);
    const minimo = grupo.obligatorio ? Math.max(1, minimoConfigurado) : minimoConfigurado;
    const maximo = grupo.maximo_selecciones === null
      ? null
      : Number(grupo.maximo_selecciones);

    if (cantidad < minimo) {
      errores[comoId(grupo.id)] = `Selecciona al menos ${minimo} ${minimo === 1 ? "opción" : "opciones"}.`;
    } else if (maximo !== null && cantidad > maximo) {
      errores[comoId(grupo.id)] = `Selecciona como máximo ${maximo} ${maximo === 1 ? "opción" : "opciones"}.`;
    }
  });

  return { valida: Object.keys(errores).length === 0, errores };
};

export const obtenerOpcionesSeleccionadas = (grupos = [], selecciones = {}) => {
  const resultado = [];
  grupos.forEach((grupo) => {
    const idsGrupo = new Set(obtenerSeleccionGrupo(selecciones, grupo.id));
    (grupo.opciones || []).forEach((opcion) => {
      if (opcion.disponible !== false && idsGrupo.has(comoId(opcion.id))) {
        resultado.push({ grupo, opcion });
      }
    });
  });
  return resultado;
};

export const obtenerIdsOpciones = (grupos = [], selecciones = {}) =>
  obtenerOpcionesSeleccionadas(grupos, selecciones)
    .map(({ opcion }) => Number(opcion.id))
    .sort((a, b) => a - b);

export const calcularPrecioOpciones = (grupos = [], selecciones = {}) =>
  obtenerOpcionesSeleccionadas(grupos, selecciones)
    .reduce((total, { opcion }) => total + Number(opcion.precio_adicional || 0), 0);

export const calcularPrecioConfigurado = (producto, variante, selecciones = {}) => {
  const precioBase = obtenerPrecioEfectivo(variante || producto);
  return precioBase + calcularPrecioOpciones(gruposPersonalizacion(producto), selecciones);
};

export const calcularPrecioConfiguradoOriginal = (producto, variante, selecciones = {}) => {
  const precioBase = obtenerPrecioOriginal(variante || producto);
  return precioBase + calcularPrecioOpciones(gruposPersonalizacion(producto), selecciones);
};

export const construirResumenOpciones = (grupos = [], selecciones = {}) =>
  grupos.map((grupo) => {
    const idsGrupo = new Set(obtenerSeleccionGrupo(selecciones, grupo.id));
    const opciones = (grupo.opciones || [])
      .filter((opcion) => opcion.disponible !== false && idsGrupo.has(comoId(opcion.id)))
      .map((opcion) => ({
        opcion_id: Number(opcion.id),
        nombre: opcion.nombre,
        precio_adicional: Number(opcion.precio_adicional || 0),
      }));

    return opciones.length
      ? { grupo_id: Number(grupo.id), grupo_nombre: grupo.nombre, opciones }
      : null;
  }).filter(Boolean);

export const crearClaveCarrito = (productoId, varianteId, opcionIds = []) => {
  const opcionesCanonicas = [...opcionIds].map(Number).sort((a, b) => a - b);
  return `${productoId}:${varianteId ?? "base"}:${opcionesCanonicas.join(",")}`;
};
