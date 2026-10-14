import { authFetch, readJsonResponse } from "../api";

const gruposPath = (productoId) =>
  `/mi-restaurante/productos/${productoId}/grupos-opciones/`;

const grupoPath = (productoId, grupoId) =>
  `${gruposPath(productoId)}${grupoId}/`;

const opcionesPath = (productoId, grupoId) =>
  `${grupoPath(productoId, grupoId)}opciones/`;

const opcionPath = (productoId, grupoId, opcionId) =>
  `${opcionesPath(productoId, grupoId)}${opcionId}/`;

async function solicitar(path, options, fallback) {
  const response = await authFetch(path, options);
  return readJsonResponse(response, path, fallback);
}

export const listarGruposOpciones = (productoId) =>
  solicitar(gruposPath(productoId), {}, "No se pudieron cargar los grupos de personalización.");

export const crearGrupoOpciones = (productoId, payload) =>
  solicitar(
    gruposPath(productoId),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "No se pudo crear el grupo de personalización.",
  );

export const actualizarGrupoOpciones = (productoId, grupoId, payload) =>
  solicitar(
    grupoPath(productoId, grupoId),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "No se pudo actualizar el grupo de personalización.",
  );

export const eliminarGrupoOpciones = (productoId, grupoId) =>
  solicitar(
    grupoPath(productoId, grupoId),
    { method: "DELETE" },
    "No se pudo eliminar el grupo de personalización.",
  );

export const crearOpcionProducto = (productoId, grupoId, payload) =>
  solicitar(
    opcionesPath(productoId, grupoId),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "No se pudo crear la opción.",
  );

export const actualizarOpcionProducto = (productoId, grupoId, opcionId, payload) =>
  solicitar(
    opcionPath(productoId, grupoId, opcionId),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "No se pudo actualizar la opción.",
  );

export const eliminarOpcionProducto = (productoId, grupoId, opcionId) =>
  solicitar(
    opcionPath(productoId, grupoId, opcionId),
    { method: "DELETE" },
    "No se pudo eliminar la opción.",
  );

export async function crearPersonalizacionProducto(productoId, grupos) {
  for (const grupo of [...grupos].sort((a, b) => Number(a.orden) - Number(b.orden))) {
    const grupoCreado = await crearGrupoOpciones(productoId, {
      nombre: grupo.nombre.trim(),
      obligatorio: Boolean(grupo.obligatorio),
      minimo_selecciones: Number(grupo.minimo_selecciones),
      maximo_selecciones:
        grupo.maximo_selecciones === null ? null : Number(grupo.maximo_selecciones),
      orden: Number(grupo.orden),
    });

    for (const opcion of [...(grupo.opciones || [])].sort(
      (a, b) => Number(a.orden) - Number(b.orden),
    )) {
      await crearOpcionProducto(productoId, grupoCreado.id, {
        nombre: opcion.nombre.trim(),
        precio_adicional: Number(opcion.precio_adicional),
        disponible: opcion.disponible !== false,
        orden: Number(opcion.orden),
      });
    }
  }
}
