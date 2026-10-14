const comoId = (valor) => String(valor);

export const obtenerGruposSnapshot = (itemOrGrupos) => {
  if (Array.isArray(itemOrGrupos)) return itemOrGrupos;
  if (Array.isArray(itemOrGrupos?.grupos_opciones)) return itemOrGrupos.grupos_opciones;
  if (Array.isArray(itemOrGrupos?.opciones_snapshot)) return itemOrGrupos.opciones_snapshot;
  return [];
};

export const obtenerIdsOpcionesSnapshot = (itemOrGrupos) => (
  obtenerGruposSnapshot(itemOrGrupos)
    .flatMap((grupo) => grupo?.opciones || [])
    .map((opcion) => Number(opcion?.opcion_id ?? opcion?.id))
    .filter(Number.isFinite)
    .sort((a, b) => a - b)
);

export const crearClaveLineaPedido = (productoId, varianteId, opciones = []) => {
  const ids = Array.isArray(opciones)
    ? opciones.map((opcion) => Number(opcion)).filter(Number.isFinite).sort((a, b) => a - b)
    : [];
  return `${productoId}:${varianteId || "base"}:${ids.join(",")}`;
};

export const obtenerTextoSeleccion = (grupo) => {
  const minimoConfigurado = Math.max(0, Number(grupo?.minimo_selecciones) || 0);
  const minimo = grupo?.obligatorio ? Math.max(1, minimoConfigurado) : minimoConfigurado;
  const maximo = grupo?.maximo_selecciones === null
    ? null
    : Math.max(0, Number(grupo?.maximo_selecciones) || 0);

  if (minimo === 1 && maximo === 1) return "Elige 1";
  if (minimo > 0 && maximo !== null && minimo !== maximo) return `Elige entre ${minimo} y ${maximo}`;
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
  const maximo = grupo.maximo_selecciones === null ? null : Number(grupo.maximo_selecciones);
  let siguientes;

  if (maximo === 1) siguientes = [opcionNormalizada];
  else if (yaSeleccionada) siguientes = actuales.filter((id) => id !== opcionNormalizada);
  else if (maximo !== null && actuales.length >= maximo) siguientes = actuales;
  else siguientes = [...actuales, opcionNormalizada];

  return { ...(selecciones || {}), [grupoId]: siguientes };
};

export const validarSelecciones = (grupos = [], selecciones = {}) => {
  const errores = {};
  grupos.forEach((grupo) => {
    const disponibles = new Set(
      (grupo.opciones || []).filter((opcion) => opcion.disponible !== false).map((opcion) => comoId(opcion.id))
    );
    const cantidad = obtenerSeleccionGrupo(selecciones, grupo.id).filter((id) => disponibles.has(id)).length;
    const minimoConfigurado = Math.max(0, Number(grupo.minimo_selecciones) || 0);
    const minimo = grupo.obligatorio ? Math.max(1, minimoConfigurado) : minimoConfigurado;
    const maximo = grupo.maximo_selecciones === null ? null : Number(grupo.maximo_selecciones);
    if (cantidad < minimo) errores[comoId(grupo.id)] = `Selecciona al menos ${minimo} opcion(es).`;
    else if (maximo !== null && cantidad > maximo) errores[comoId(grupo.id)] = `Selecciona como maximo ${maximo} opcion(es).`;
  });
  return errores;
};

export const obtenerOpcionesCatalogoSeleccionadas = (grupos = [], selecciones = {}) => (
  grupos.flatMap((grupo) => {
    const seleccionadas = new Set(obtenerSeleccionGrupo(selecciones, grupo.id));
    return (grupo.opciones || [])
      .filter((opcion) => opcion.disponible !== false && seleccionadas.has(comoId(opcion.id)))
      .map((opcion) => ({ grupo, opcion }));
  })
);

export const obtenerIdsOpcionesCatalogo = (grupos = [], selecciones = {}) => (
  obtenerOpcionesCatalogoSeleccionadas(grupos, selecciones)
    .map(({ opcion }) => Number(opcion.id))
    .sort((a, b) => a - b)
);

export const calcularAdicionalOpciones = (grupos = [], selecciones = {}) => (
  obtenerOpcionesCatalogoSeleccionadas(grupos, selecciones)
    .reduce((total, { opcion }) => total + Number(opcion.precio_adicional || 0), 0)
);

export const construirSnapshotVisual = (grupos = [], selecciones = {}) => (
  grupos.map((grupo) => {
    const opciones = obtenerOpcionesCatalogoSeleccionadas([grupo], selecciones).map(({ opcion }) => ({
      opcion_id: Number(opcion.id),
      nombre: opcion.nombre,
      precio_adicional: Number(opcion.precio_adicional || 0),
    }));
    return opciones.length ? { grupo_id: Number(grupo.id), grupo_nombre: grupo.nombre, opciones } : null;
  }).filter(Boolean)
);

