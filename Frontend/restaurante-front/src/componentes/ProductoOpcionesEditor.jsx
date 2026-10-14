import { useEffect, useMemo, useState } from "react";
import {
  actualizarGrupoOpciones,
  actualizarOpcionProducto,
  crearGrupoOpciones,
  crearOpcionProducto,
  eliminarGrupoOpciones,
  eliminarOpcionProducto,
  listarGruposOpciones,
} from "../api/productoOpciones";

const crearKey = (prefijo) =>
  `${prefijo}-${Date.now()}-${Math.random().toString(16).slice(2)}`;

const grupoVacio = (orden = 0) => ({
  nombre: "",
  obligatorio: false,
  minimo_selecciones: 0,
  maximo_selecciones: 1,
  orden,
  opciones: [],
});

const opcionVacia = (orden = 0) => ({
  nombre: "",
  precio_adicional: 0,
  disponible: true,
  orden,
});

const ordenar = (items = []) =>
  [...items].sort((a, b) => Number(a.orden) - Number(b.orden) || Number(a.id || 0) - Number(b.id || 0));

const formatearCLP = (valor) =>
  new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(Number(valor) || 0);

function ModalBase({ tituloSuperior, titulo, error, onCancel, children, footer }) {
  useEffect(() => {
    const cerrarConEscape = (event) => event.key === "Escape" && onCancel();
    document.body.classList.add("modal-open");
    window.addEventListener("keydown", cerrarConEscape);
    return () => {
      document.body.classList.remove("modal-open");
      window.removeEventListener("keydown", cerrarConEscape);
    };
  }, [onCancel]);

  return (
    <div
      className="opciones-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onCancel()}
    >
      <section className="opciones-modal" role="dialog" aria-modal="true" aria-labelledby="opciones-modal-title">
        <header className="opciones-modal-header">
          <div>
            <span>{tituloSuperior}</span>
            <h2 id="opciones-modal-title">{titulo}</h2>
          </div>
          <button type="button" className="opciones-icon-button" onClick={onCancel} aria-label="Cerrar modal">
            <i className="bi bi-x-lg" aria-hidden="true"></i>
          </button>
        </header>
        <div className="opciones-modal-body">
          {error && <div className="opciones-alert is-error" role="alert">{error}</div>}
          {children}
        </div>
        <footer className="opciones-modal-footer">{footer}</footer>
      </section>
    </div>
  );
}

function GrupoModal({ grupo, nombresExistentes, guardando, error, onCancel, onSave }) {
  const [form, setForm] = useState({ ...grupo });
  const [sinMaximo, setSinMaximo] = useState(grupo.maximo_selecciones === null);
  const [errores, setErrores] = useState({});

  const actualizar = (campo, valor) => {
    setForm((actual) => ({ ...actual, [campo]: valor }));
    setErrores((actuales) => ({ ...actuales, [campo]: "" }));
  };

  const guardar = () => {
    const nuevosErrores = {};
    const nombre = form.nombre.trim();
    const minimo = Number(form.minimo_selecciones);
    const maximo = sinMaximo ? null : Number(form.maximo_selecciones);
    const orden = Number(form.orden);

    if (!nombre) nuevosErrores.nombre = "El nombre es obligatorio.";
    else if (nombresExistentes.includes(nombre.toLowerCase())) {
      nuevosErrores.nombre = "Ya existe un grupo con este nombre.";
    }
    if (!Number.isInteger(minimo) || minimo < 0) {
      nuevosErrores.minimo_selecciones = "El mínimo debe ser un entero mayor o igual a 0.";
    } else if (form.obligatorio && minimo < 1) {
      nuevosErrores.minimo_selecciones = "Un grupo obligatorio debe requerir al menos una selección.";
    }
    if (!sinMaximo && (!Number.isInteger(maximo) || maximo < 1)) {
      nuevosErrores.maximo_selecciones = "El máximo debe ser un entero mayor o igual a 1.";
    } else if (!sinMaximo && Number.isInteger(minimo) && maximo < minimo) {
      nuevosErrores.maximo_selecciones = "El máximo debe ser mayor o igual al mínimo.";
    }
    if (!Number.isInteger(orden) || orden < 0) {
      nuevosErrores.orden = "El orden debe ser un entero mayor o igual a 0.";
    }

    if (Object.keys(nuevosErrores).length) {
      setErrores(nuevosErrores);
      return;
    }

    onSave({
      ...form,
      nombre,
      minimo_selecciones: minimo,
      maximo_selecciones: maximo,
      orden,
    });
  };

  return (
    <ModalBase
      tituloSuperior="Personalización del producto"
      titulo={grupo.id || grupo._key ? "Editar grupo" : "Agregar grupo"}
      error={error}
      onCancel={onCancel}
      footer={(
        <>
          <button type="button" className="opciones-secondary-button" onClick={onCancel} disabled={guardando}>Cancelar</button>
          <button type="button" className="opciones-primary-button" onClick={guardar} disabled={guardando}>
            {guardando ? "Guardando..." : "Guardar grupo"}
          </button>
        </>
      )}
    >
      <div className="opciones-field">
        <label htmlFor="grupo-nombre">Nombre <span>*</span></label>
        <input id="grupo-nombre" className={`form-control ${errores.nombre ? "is-invalid" : ""}`} value={form.nombre} placeholder="Ej: Proteínas" onChange={(event) => actualizar("nombre", event.target.value)} autoFocus />
        {errores.nombre && <small className="opciones-field-error">{errores.nombre}</small>}
      </div>

      <label className="opciones-toggle-control">
        <span><strong>Grupo obligatorio</strong><small>El cliente deberá respetar el mínimo configurado.</small></span>
        <input className="form-check-input" type="checkbox" checked={form.obligatorio} onChange={(event) => actualizar("obligatorio", event.target.checked)} />
      </label>

      <div className="opciones-modal-grid">
        <div className="opciones-field">
          <label htmlFor="grupo-minimo">Mínimo <span>*</span></label>
          <input id="grupo-minimo" className={`form-control ${errores.minimo_selecciones ? "is-invalid" : ""}`} type="number" min="0" step="1" value={form.minimo_selecciones} onChange={(event) => actualizar("minimo_selecciones", event.target.value)} />
          {errores.minimo_selecciones && <small className="opciones-field-error">{errores.minimo_selecciones}</small>}
        </div>
        <div className="opciones-field">
          <label htmlFor="grupo-maximo">Máximo</label>
          <input id="grupo-maximo" className={`form-control ${errores.maximo_selecciones ? "is-invalid" : ""}`} type="number" min="1" step="1" value={sinMaximo ? "" : form.maximo_selecciones} onChange={(event) => actualizar("maximo_selecciones", event.target.value)} disabled={sinMaximo} />
          {errores.maximo_selecciones && <small className="opciones-field-error">{errores.maximo_selecciones}</small>}
        </div>
      </div>

      <label className="opciones-inline-check">
        <input
          type="checkbox"
          checked={sinMaximo}
          onChange={(event) => {
            const activo = event.target.checked;
            setSinMaximo(activo);
            if (!activo && form.maximo_selecciones === null) {
              actualizar("maximo_selecciones", Math.max(1, Number(form.minimo_selecciones) || 0));
            }
          }}
        />
        Sin máximo de selecciones
      </label>

      <div className="opciones-field">
        <label htmlFor="grupo-orden">Orden <span>*</span></label>
        <input id="grupo-orden" className={`form-control ${errores.orden ? "is-invalid" : ""}`} type="number" min="0" step="1" value={form.orden} onChange={(event) => actualizar("orden", event.target.value)} />
        <small>Los grupos se muestran de menor a mayor.</small>
        {errores.orden && <small className="opciones-field-error">{errores.orden}</small>}
      </div>
    </ModalBase>
  );
}

function OpcionModal({ opcion, nombresExistentes, guardando, error, onCancel, onSave }) {
  const [form, setForm] = useState({ ...opcion });
  const [errores, setErrores] = useState({});

  const actualizar = (campo, valor) => {
    setForm((actual) => ({ ...actual, [campo]: valor }));
    setErrores((actuales) => ({ ...actuales, [campo]: "" }));
  };

  const guardar = () => {
    const nuevosErrores = {};
    const nombre = form.nombre.trim();
    const precio = Number(form.precio_adicional);
    const orden = Number(form.orden);

    if (!nombre) nuevosErrores.nombre = "El nombre es obligatorio.";
    else if (nombresExistentes.includes(nombre.toLowerCase())) {
      nuevosErrores.nombre = "Ya existe una opción con este nombre en el grupo.";
    }
    if (form.precio_adicional === "" || !Number.isFinite(precio) || precio < 0) {
      nuevosErrores.precio_adicional = "El precio adicional debe ser mayor o igual a 0.";
    }
    if (!Number.isInteger(orden) || orden < 0) {
      nuevosErrores.orden = "El orden debe ser un entero mayor o igual a 0.";
    }

    if (Object.keys(nuevosErrores).length) {
      setErrores(nuevosErrores);
      return;
    }

    onSave({ ...form, nombre, precio_adicional: precio, orden });
  };

  return (
    <ModalBase
      tituloSuperior="Opción del grupo"
      titulo={opcion.id || opcion._key ? "Editar opción" : "Agregar opción"}
      error={error}
      onCancel={onCancel}
      footer={(
        <>
          <button type="button" className="opciones-secondary-button" onClick={onCancel} disabled={guardando}>Cancelar</button>
          <button type="button" className="opciones-primary-button" onClick={guardar} disabled={guardando}>
            {guardando ? "Guardando..." : "Guardar opción"}
          </button>
        </>
      )}
    >
      <div className="opciones-field">
        <label htmlFor="opcion-nombre">Nombre <span>*</span></label>
        <input id="opcion-nombre" className={`form-control ${errores.nombre ? "is-invalid" : ""}`} value={form.nombre} placeholder="Ej: Queso extra" onChange={(event) => actualizar("nombre", event.target.value)} autoFocus />
        {errores.nombre && <small className="opciones-field-error">{errores.nombre}</small>}
      </div>
      <div className="opciones-modal-grid">
        <div className="opciones-field">
          <label htmlFor="opcion-precio">Precio adicional <span>*</span></label>
          <div className="input-group">
            <span className="input-group-text">$</span>
            <input id="opcion-precio" className={`form-control ${errores.precio_adicional ? "is-invalid" : ""}`} type="number" min="0" step="1" value={form.precio_adicional} onChange={(event) => actualizar("precio_adicional", event.target.value)} />
          </div>
          {errores.precio_adicional && <small className="opciones-field-error">{errores.precio_adicional}</small>}
        </div>
        <div className="opciones-field">
          <label htmlFor="opcion-orden">Orden <span>*</span></label>
          <input id="opcion-orden" className={`form-control ${errores.orden ? "is-invalid" : ""}`} type="number" min="0" step="1" value={form.orden} onChange={(event) => actualizar("orden", event.target.value)} />
          {errores.orden && <small className="opciones-field-error">{errores.orden}</small>}
        </div>
      </div>
      <label className="opciones-toggle-control">
        <span><strong>Disponible</strong><small>Puede desactivarse temporalmente sin eliminarla.</small></span>
        <input className="form-check-input" type="checkbox" checked={form.disponible !== false} onChange={(event) => actualizar("disponible", event.target.checked)} />
      </label>
    </ModalBase>
  );
}

export default function ProductoOpcionesEditor({ productoId = null, grupos = [], onChange = () => {} }) {
  const [gruposPersistidos, setGruposPersistidos] = useState([]);
  const [cargando, setCargando] = useState(Boolean(productoId));
  const [operacion, setOperacion] = useState("");
  const [error, setError] = useState("");
  const [exito, setExito] = useState("");
  const [modalGrupo, setModalGrupo] = useState(null);
  const [modalOpcion, setModalOpcion] = useState(null);

  const gruposActuales = productoId ? gruposPersistidos : grupos;
  const gruposOrdenados = useMemo(() => ordenar(gruposActuales), [gruposActuales]);

  useEffect(() => {
    if (!productoId) return undefined;
    let activo = true;
    listarGruposOpciones(productoId)
      .then((data) => activo && setGruposPersistidos(data || []))
      .catch((requestError) => activo && setError(requestError.message))
      .finally(() => activo && setCargando(false));
    return () => { activo = false; };
  }, [productoId]);

  const reemplazarGrupos = (siguiente) => {
    if (productoId) setGruposPersistidos(siguiente);
    else onChange(siguiente);
  };

  const comenzar = (nombre) => {
    setOperacion(nombre);
    setError("");
    setExito("");
  };

  const finalizarConError = (requestError) => {
    setError(requestError.message || "No se pudo completar la operación.");
    setOperacion("");
  };

  const abrirGrupoNuevo = () => setModalGrupo({ index: null, grupo: grupoVacio(gruposActuales.length) });
  const abrirGrupoEdicion = (grupo) => setModalGrupo({ grupo, index: gruposActuales.indexOf(grupo) });

  const guardarGrupo = async (grupo) => {
    comenzar("grupo");
    try {
      if (productoId) {
        const payload = {
          nombre: grupo.nombre,
          obligatorio: grupo.obligatorio,
          minimo_selecciones: grupo.minimo_selecciones,
          maximo_selecciones: grupo.maximo_selecciones,
          orden: grupo.orden,
        };
        const guardado = grupo.id
          ? await actualizarGrupoOpciones(productoId, grupo.id, payload)
          : await crearGrupoOpciones(productoId, payload);
        reemplazarGrupos(
          grupo.id
            ? gruposActuales.map((actual) => actual.id === grupo.id ? guardado : actual)
            : [...gruposActuales, guardado],
        );
      } else if (modalGrupo.index === null) {
        reemplazarGrupos([...gruposActuales, { ...grupo, _key: crearKey("grupo") }]);
      } else {
        reemplazarGrupos(gruposActuales.map((actual, index) =>
          index === modalGrupo.index ? { ...grupo, _key: actual._key } : actual));
      }
      setModalGrupo(null);
      setExito(
        productoId
          ? "Grupo guardado correctamente."
          : "Grupo agregado al borrador. Se guardará al crear el producto.",
      );
      setOperacion("");
    } catch (requestError) {
      finalizarConError(requestError);
    }
  };

  const eliminarGrupo = async (grupo) => {
    const confirmado = window.confirm(
      `¿Eliminar el grupo ${grupo.nombre}?\n\nTambién se eliminarán las opciones asociadas a este grupo.\nLos pedidos históricos no serán modificados.`,
    );
    if (!confirmado) return;
    comenzar(`eliminar-grupo-${grupo.id || grupo._key}`);
    try {
      if (productoId) await eliminarGrupoOpciones(productoId, grupo.id);
      reemplazarGrupos(gruposActuales.filter((actual) => actual !== grupo));
      setExito("Grupo eliminado correctamente.");
      setOperacion("");
    } catch (requestError) {
      finalizarConError(requestError);
    }
  };

  const abrirOpcionNueva = (grupo) => setModalOpcion({ grupo, opcion: opcionVacia((grupo.opciones || []).length), index: null });
  const abrirOpcionEdicion = (grupo, opcion) => setModalOpcion({ grupo, opcion, index: (grupo.opciones || []).indexOf(opcion) });

  const actualizarGrupoLocal = (grupo, cambios) =>
    reemplazarGrupos(gruposActuales.map((actual) => actual === grupo ? { ...actual, ...cambios } : actual));

  const guardarOpcion = async (opcion) => {
    const { grupo, index } = modalOpcion;
    comenzar("opcion");
    try {
      if (productoId) {
        const payload = {
          nombre: opcion.nombre,
          precio_adicional: opcion.precio_adicional,
          disponible: opcion.disponible,
          orden: opcion.orden,
        };
        const guardada = opcion.id
          ? await actualizarOpcionProducto(productoId, grupo.id, opcion.id, payload)
          : await crearOpcionProducto(productoId, grupo.id, payload);
        actualizarGrupoLocal(grupo, {
          opciones: opcion.id
            ? grupo.opciones.map((actual) => actual.id === opcion.id ? guardada : actual)
            : [...(grupo.opciones || []), guardada],
        });
      } else {
        const opciones = index === null
          ? [...(grupo.opciones || []), { ...opcion, _key: crearKey("opcion") }]
          : grupo.opciones.map((actual, posicion) =>
            posicion === index ? { ...opcion, _key: actual._key } : actual);
        actualizarGrupoLocal(grupo, { opciones });
      }
      setModalOpcion(null);
      setExito(
        productoId
          ? "Opción guardada correctamente."
          : "Opción agregada al borrador. Se guardará al crear el producto.",
      );
      setOperacion("");
    } catch (requestError) {
      finalizarConError(requestError);
    }
  };

  const cambiarDisponibilidad = async (grupo, opcion) => {
    const disponible = opcion.disponible === false;
    comenzar(`disponibilidad-${opcion.id || opcion._key}`);
    try {
      let actualizada = { ...opcion, disponible };
      if (productoId) {
        actualizada = await actualizarOpcionProducto(productoId, grupo.id, opcion.id, { disponible });
      }
      actualizarGrupoLocal(grupo, {
        opciones: grupo.opciones.map((actual) => actual === opcion ? actualizada : actual),
      });
      setExito(disponible ? "Opción activada." : "Opción desactivada.");
      setOperacion("");
    } catch (requestError) {
      finalizarConError(requestError);
    }
  };

  const eliminarOpcion = async (grupo, opcion) => {
    if (!window.confirm(`¿Eliminar la opción ${opcion.nombre}?\nLos pedidos históricos no serán modificados.`)) return;
    comenzar(`eliminar-opcion-${opcion.id || opcion._key}`);
    try {
      if (productoId) await eliminarOpcionProducto(productoId, grupo.id, opcion.id);
      actualizarGrupoLocal(grupo, { opciones: grupo.opciones.filter((actual) => actual !== opcion) });
      setExito("Opción eliminada correctamente.");
      setOperacion("");
    } catch (requestError) {
      finalizarConError(requestError);
    }
  };

  const grupoEditado = modalGrupo?.grupo;
  const nombresGrupos = grupoEditado
    ? gruposActuales.filter((grupo) => grupo !== grupoEditado).map((grupo) => grupo.nombre.trim().toLowerCase())
    : [];
  const opcionEditada = modalOpcion?.opcion;
  const nombresOpciones = modalOpcion
    ? (modalOpcion.grupo.opciones || []).filter((opcion) => opcion !== opcionEditada).map((opcion) => opcion.nombre.trim().toLowerCase())
    : [];

  return (
    <div className="form mt-4 opciones-editor">
      <div className="opciones-editor-header">
        <div>
          <p className="info-header"><span><i className="bi bi-ui-checks-grid"></i></span>{" "}Personalización del producto</p>
          <small>{productoId ? "Administra grupos y opciones disponibles para este producto." : "Opcional. Se guardará después de crear el producto y sus variantes."}</small>
        </div>
        <button type="button" className="opciones-primary-button" onClick={abrirGrupoNuevo} disabled={Boolean(operacion) || cargando}>
          <i className="bi bi-plus-lg" aria-hidden="true"></i> Agregar grupo
        </button>
      </div>

      {error && <div className="opciones-alert is-error" role="alert">{error}</div>}
      {exito && <div className="opciones-alert is-success" role="status">{exito}</div>}

      {cargando ? (
        <p className="opciones-empty">Cargando grupos de personalización...</p>
      ) : gruposOrdenados.length === 0 ? (
        <p className="opciones-empty">No hay grupos de personalización configurados.</p>
      ) : (
        <div className="opciones-groups">
          {gruposOrdenados.map((grupo) => (
            <article className="opciones-group-card" key={grupo.id || grupo._key}>
              <header className="opciones-group-header">
                <div>
                  <div className="opciones-group-title">
                    <h3>{grupo.nombre}</h3>
                    <span className={`opciones-badge ${grupo.obligatorio ? "is-required" : ""}`}>
                      {grupo.obligatorio ? "Obligatorio" : "Opcional"}
                    </span>
                  </div>
                  <p>
                    Mínimo {grupo.minimo_selecciones} · Máximo {grupo.maximo_selecciones === null ? "sin máximo" : grupo.maximo_selecciones} · Orden {grupo.orden}
                  </p>
                </div>
                <div className="opciones-card-actions">
                  <button type="button" className="opciones-icon-button" onClick={() => abrirGrupoEdicion(grupo)} disabled={Boolean(operacion)} title="Editar grupo" aria-label={`Editar grupo ${grupo.nombre}`}><i className="bi bi-pencil-square"></i></button>
                  <button type="button" className="opciones-icon-button is-danger" onClick={() => eliminarGrupo(grupo)} disabled={Boolean(operacion)} title="Eliminar grupo" aria-label={`Eliminar grupo ${grupo.nombre}`}><i className="bi bi-trash3"></i></button>
                </div>
              </header>

              <div className="opciones-list-heading">
                <strong>Opciones</strong>
                <button type="button" className="opciones-link-button" onClick={() => abrirOpcionNueva(grupo)} disabled={Boolean(operacion)}>
                  <i className="bi bi-plus-lg"></i> Agregar opción
                </button>
              </div>

              {(grupo.opciones || []).length === 0 ? (
                <p className="opciones-group-empty">Este grupo todavía no tiene opciones.</p>
              ) : (
                <div className="opciones-list" role="table" aria-label={`Opciones de ${grupo.nombre}`}>
                  {ordenar(grupo.opciones).map((opcion) => (
                    <div className="opciones-list-row" role="row" key={opcion.id || opcion._key}>
                      <div className="opciones-list-name" role="cell" data-label="Opción">
                        <strong>{opcion.nombre}</strong>
                        <small>Orden {opcion.orden}</small>
                      </div>
                      <span role="cell" data-label="Adicional">{Number(opcion.precio_adicional) > 0 ? `+${formatearCLP(opcion.precio_adicional)}` : formatearCLP(0)}</span>
                      <label className="opciones-availability" role="cell" data-label="Disponible">
                        <input className="form-check-input" type="checkbox" checked={opcion.disponible !== false} onChange={() => cambiarDisponibilidad(grupo, opcion)} disabled={Boolean(operacion)} />
                        <span>{opcion.disponible !== false ? "Disponible" : "No disponible"}</span>
                      </label>
                      <div className="opciones-card-actions" role="cell" data-label="Acciones">
                        <button type="button" className="opciones-icon-button" onClick={() => abrirOpcionEdicion(grupo, opcion)} disabled={Boolean(operacion)} title="Editar opción" aria-label={`Editar opción ${opcion.nombre}`}><i className="bi bi-pencil-square"></i></button>
                        <button type="button" className="opciones-icon-button is-danger" onClick={() => eliminarOpcion(grupo, opcion)} disabled={Boolean(operacion)} title="Eliminar opción" aria-label={`Eliminar opción ${opcion.nombre}`}><i className="bi bi-trash3"></i></button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}

      {modalGrupo && (
        <GrupoModal
          grupo={modalGrupo.grupo}
          nombresExistentes={nombresGrupos}
          guardando={operacion === "grupo"}
          error={error}
          onCancel={() => !operacion && setModalGrupo(null)}
          onSave={guardarGrupo}
        />
      )}
      {modalOpcion && (
        <OpcionModal
          opcion={modalOpcion.opcion}
          nombresExistentes={nombresOpciones}
          guardando={operacion === "opcion"}
          error={error}
          onCancel={() => !operacion && setModalOpcion(null)}
          onSave={guardarOpcion}
        />
      )}
    </div>
  );
}
