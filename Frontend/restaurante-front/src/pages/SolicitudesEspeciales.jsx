import { useCallback, useEffect, useMemo, useState } from "react";
import "../styles/ReservasDashboard.css";
import MainMenu from "../componentes/Main-menu";
import { authFetch } from "../api";

const ESTADOS = ["pendiente", "en_revision", "aceptada", "rechazada", "completada"];

const estadoLabels = {
  pendiente: "Pendiente",
  en_revision: "En revisión",
  aceptada: "Aceptada",
  rechazada: "Rechazada",
  completada: "Completada",
};

const formularioInicial = {
  nombre: "",
  apellido: "",
  fecha_evento: "",
  telefono_contacto: "",
  email_contacto: "",
  descripcion_solicitud: "",
  estado: "pendiente",
};

const pedidoEspecialInicial = {
  fecha_entrega: "",
  items: [{ nombre: "", descripcion: "", cantidad: 1, precio_unitario: 0 }],
};

const obtenerMensajeError = async (response, fallback) => {
  try {
    const data = await response.json();
    return data?.error || data?.detail || fallback;
  } catch {
    return fallback;
  }
};

export default function SolicitudesEspecialesDashboard() {
  const [solicitudes, setSolicitudes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [paginaActual, setPaginaActual] = useState(1);
  const [totalSolicitudes, setTotalSolicitudes] = useState(0);
  const [paginaSiguiente, setPaginaSiguiente] = useState(null);
  const [paginaAnterior, setPaginaAnterior] = useState(null);
  const [busqueda, setBusqueda] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("todas");
  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [modoModal, setModoModal] = useState("crear");
  const [solicitudEditando, setSolicitudEditando] = useState(null);
  const [formSolicitud, setFormSolicitud] = useState(formularioInicial);
  const [solicitudPedido, setSolicitudPedido] = useState(null);
  const [formPedidoEspecial, setFormPedidoEspecial] = useState(pedidoEspecialInicial);

  const cargarSolicitudes = useCallback(async (page = paginaActual) => {
    setLoading(true);
    setError("");

    try {
      const response = await authFetch(`/mi-restaurante/solicitudes-especiales/?page=${page}`);

      if (!response.ok) {
        throw new Error(
          await obtenerMensajeError(response, "No se pudieron cargar las solicitudes.")
        );
      }

      const data = await response.json();
      setSolicitudes(data.results || data);
      setTotalSolicitudes(data.count ?? (Array.isArray(data) ? data.length : 0));
      setPaginaSiguiente(data.next || null);
      setPaginaAnterior(data.previous || null);
    } catch (requestError) {
      setSolicitudes([]);
      setTotalSolicitudes(0);
      setPaginaSiguiente(null);
      setPaginaAnterior(null);
      setError(requestError.message || "No se pudieron cargar las solicitudes.");
    } finally {
      setLoading(false);
    }
  }, [paginaActual]);

  useEffect(() => {
    cargarSolicitudes();
  }, [cargarSolicitudes]);

  const solicitudesFiltradas = useMemo(() => {
    return solicitudes.filter((solicitud) => {
      const texto = [
        solicitud.nombre,
        solicitud.apellido,
        solicitud.telefono_contacto,
        solicitud.email_contacto,
        solicitud.descripcion_solicitud,
      ].join(" ").toLowerCase();

      const coincideBusqueda = texto.includes(busqueda.toLowerCase());
      const coincideEstado = filtroEstado === "todas" || solicitud.estado === filtroEstado;

      return coincideBusqueda && coincideEstado;
    });
  }, [busqueda, filtroEstado, solicitudes]);

  const conteos = useMemo(() => {
    return ESTADOS.reduce((acc, estado) => {
      acc[estado] = solicitudes.filter((solicitud) => solicitud.estado === estado).length;
      return acc;
    }, {});
  }, [solicitudes]);

  const abrirCrearSolicitud = () => {
    setModoModal("crear");
    setSolicitudEditando(null);
    setFormSolicitud(formularioInicial);
    setMostrarFormulario(true);
    setError("");
    setMensaje("");
  };

  const abrirEditarSolicitud = (solicitud) => {
    setModoModal("editar");
    setSolicitudEditando(solicitud);
    setFormSolicitud({
      nombre: solicitud.nombre || "",
      apellido: solicitud.apellido || "",
      fecha_evento: solicitud.fecha_evento || "",
      telefono_contacto: solicitud.telefono_contacto || "",
      email_contacto: solicitud.email_contacto || "",
      descripcion_solicitud: solicitud.descripcion_solicitud || "",
      estado: solicitud.estado || "pendiente",
    });
    setMostrarFormulario(true);
    setError("");
    setMensaje("");
  };

  const validarFormulario = () => {
    const requeridos = [
      "nombre",
      "apellido",
      "fecha_evento",
      "telefono_contacto",
      "email_contacto",
      "descripcion_solicitud",
    ];

    if (requeridos.some((campo) => !String(formSolicitud[campo] || "").trim())) {
      setError("Completa todos los campos obligatorios.");
      return false;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formSolicitud.email_contacto)) {
      setError("Ingresa un email válido.");
      return false;
    }

    return true;
  };

  const guardarSolicitud = async (e) => {
    e.preventDefault();
    setError("");
    setMensaje("");

    if (!validarFormulario()) return;

    setGuardando(true);

    const esEdicion = modoModal === "editar" && solicitudEditando;
    const endpoint = esEdicion
      ? `/mi-restaurante/solicitudes-especiales/${solicitudEditando.id}/`
      : "/mi-restaurante/solicitudes-especiales/";

    try {
      const response = await authFetch(endpoint, {
        method: esEdicion ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formSolicitud),
      });

      if (!response.ok) {
        throw new Error(
          await obtenerMensajeError(response, "No se pudo guardar la solicitud.")
        );
      }

      setMensaje(esEdicion ? "Solicitud actualizada correctamente." : "Solicitud creada correctamente.");
      setMostrarFormulario(false);
      setSolicitudEditando(null);
      setFormSolicitud(formularioInicial);
      await cargarSolicitudes(paginaActual);
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar la solicitud.");
    } finally {
      setGuardando(false);
    }
  };

  const actualizarSolicitud = async (id, datos) => {
    setError("");
    setMensaje("");

    try {
      const response = await authFetch(`/mi-restaurante/solicitudes-especiales/${id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(datos),
      });

      if (!response.ok) {
        throw new Error(
          await obtenerMensajeError(response, "No se pudo actualizar la solicitud.")
        );
      }

      const data = await response.json();
      setSolicitudes((actuales) =>
        actuales.map((solicitud) =>
          solicitud.id === id ? data.solicitud : solicitud
        )
      );
      setMensaje("Solicitud actualizada correctamente.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar la solicitud.");
    }
  };

  const rechazarSolicitud = async (id) => {
    setError("");
    setMensaje("");

    try {
      const response = await authFetch(`/mi-restaurante/solicitudes-especiales/${id}/`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error(
          await obtenerMensajeError(response, "No se pudo rechazar la solicitud.")
        );
      }

      const data = await response.json();
      setSolicitudes((actuales) =>
        actuales.map((solicitud) =>
          solicitud.id === id ? data.solicitud : solicitud
        )
      );
      setMensaje("Solicitud rechazada correctamente.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo rechazar la solicitud.");
    }
  };

  const abrirConvertirPedido = (solicitud) => {
    setSolicitudPedido(solicitud);
    setFormPedidoEspecial({
      fecha_entrega: solicitud.fecha_evento || "",
      items: [{
        nombre: "Pedido especial",
        descripcion: solicitud.descripcion_solicitud || "",
        cantidad: 1,
        precio_unitario: 0,
      }],
    });
    setError("");
    setMensaje("");
  };

  const actualizarItemPedido = (index, campo, valor) => {
    setFormPedidoEspecial((actual) => ({
      ...actual,
      items: actual.items.map((item, itemIndex) => (
        itemIndex === index ? { ...item, [campo]: valor } : item
      )),
    }));
  };

  const agregarItemPedido = () => {
    setFormPedidoEspecial((actual) => ({
      ...actual,
      items: [...actual.items, { nombre: "", descripcion: "", cantidad: 1, precio_unitario: 0 }],
    }));
  };

  const quitarItemPedido = (index) => {
    setFormPedidoEspecial((actual) => ({
      ...actual,
      items: actual.items.length === 1
        ? actual.items
        : actual.items.filter((_, itemIndex) => itemIndex !== index),
    }));
  };

  const convertirEnPedidoEspecial = async (e) => {
    e.preventDefault();
    setError("");
    setMensaje("");

    const itemsValidos = formPedidoEspecial.items.every((item) =>
      String(item.nombre || "").trim() &&
      Number(item.cantidad) > 0 &&
      Number(item.precio_unitario) >= 0
    );

    if (!solicitudPedido || !formPedidoEspecial.fecha_entrega || !itemsValidos) {
      setError("Completa fecha de entrega e items del pedido.");
      return;
    }

    try {
      const response = await authFetch("/mi-restaurante/pedidos/especiales/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          solicitud_especial_id: solicitudPedido.id,
          fecha_entrega: formPedidoEspecial.fecha_entrega,
          items: formPedidoEspecial.items.map((item) => ({
            ...item,
            cantidad: Number(item.cantidad),
            precio_unitario: Number(item.precio_unitario),
          })),
        }),
      });

      if (!response.ok) {
        throw new Error(
          await obtenerMensajeError(response, "No se pudo convertir la solicitud en pedido.")
        );
      }

      setSolicitudPedido(null);
      setFormPedidoEspecial(pedidoEspecialInicial);
      setMensaje("Pedido especial creado correctamente.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo convertir la solicitud en pedido.");
    }
  };

  const exportarCSV = () => {
    const encabezados = [
      "Nombre",
      "Apellido",
      "Email",
      "Teléfono",
      "Fecha evento",
      "Estado",
      "Descripción",
    ];

    const filas = solicitudesFiltradas.map((solicitud) => [
      solicitud.nombre,
      solicitud.apellido,
      solicitud.email_contacto,
      solicitud.telefono_contacto,
      solicitud.fecha_evento,
      estadoLabels[solicitud.estado] || solicitud.estado,
      solicitud.descripcion_solicitud,
    ]);

    const csv = [encabezados, ...filas]
      .map((fila) => fila.map((dato) => `"${String(dato || "").replaceAll('"', '""')}"`).join(","))
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "solicitudes-especiales.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="body">
      <main className="container-fluid" id="main">
        <MainMenu />

        <section className="reservas-page solicitudes-page">
          <header className="reservas-header">
            <h1>Solicitudes especiales</h1>
            {error && <p className="reservas-error">{error}</p>}
            {mensaje && <p className="solicitudes-success">{mensaje}</p>}

            <div className="breadcrumb-reservas">
              <span>Inicio</span>
              <span>›</span>
              <strong>Solicitudes especiales</strong>
            </div>
          </header>

          <section className="reservas-stats solicitudes-stats">
            <div className="reserva-stat-card">
              <div className="stat-icon">
                <i className="bi bi-chat-square-text"></i>
              </div>
              <div>
                <h3>{totalSolicitudes}</h3>
                <p>Solicitudes totales</p>
              </div>
            </div>

            <div className="reserva-stat-card">
              <div className="stat-icon">
                <i className="bi bi-hourglass-split"></i>
              </div>
              <div>
                <h3>{conteos.pendiente || 0}</h3>
                <p>Pendientes</p>
              </div>
            </div>

            <div className="reserva-stat-card">
              <div className="stat-icon">
                <i className="bi bi-search"></i>
              </div>
              <div>
                <h3>{conteos.en_revision || 0}</h3>
                <p>En revisión</p>
              </div>
            </div>

            <div className="reserva-stat-card">
              <div className="stat-icon">
                <i className="bi bi-check2-circle"></i>
              </div>
              <div>
                <h3>{conteos.aceptada || 0}</h3>
                <p>Aceptadas</p>
              </div>
            </div>

            <div className="reserva-stat-card">
              <div className="stat-icon">
                <i className="bi bi-flag"></i>
              </div>
              <div>
                <h3>{(conteos.completada || 0) + (conteos.rechazada || 0)}</h3>
                <p>Cerradas</p>
              </div>
            </div>
          </section>

          <section className="reservas-tools">
            <div className="filters-row">
              <select value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)}>
                <option value="todas">Todos los estados</option>
                {ESTADOS.map((estado) => (
                  <option key={estado} value={estado}>
                    {estadoLabels[estado]}
                  </option>
                ))}
              </select>

              <div className="search-box">
                <i className="bi bi-search"></i>
                <input
                  type="search"
                  placeholder="Buscar por cliente, teléfono, email o descripción..."
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                />
              </div>

              <button className="export-btn" type="button" onClick={exportarCSV}>
                <i className="bi bi-download"></i>
                Exportar
              </button>
            </div>

            <div className="tabs-row">
              <button className={`tab ${filtroEstado === "todas" ? "active" : ""}`} onClick={() => setFiltroEstado("todas")}>
                Todas ({solicitudes.length})
              </button>
              {ESTADOS.map((estado) => (
                <button
                  key={estado}
                  className={`tab ${estado} ${filtroEstado === estado ? "active" : ""}`}
                  onClick={() => setFiltroEstado(estado)}
                >
                  {estadoLabels[estado]} ({conteos[estado] || 0})
                </button>
              ))}
              <button className="crear-reserva-btn" onClick={abrirCrearSolicitud}>
                <i className="bi bi-plus-lg"></i>
                Nueva solicitud
              </button>
            </div>
          </section>

          <section className="reservas-table-card">
            <table className="reservas-table solicitudes-table">
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Contacto</th>
                  <th>Fecha evento</th>
                  <th>Descripción</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="6" className="empty-state">Cargando solicitudes...</td>
                  </tr>
                ) : solicitudesFiltradas.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="empty-state">No hay solicitudes especiales para mostrar.</td>
                  </tr>
                ) : (
                  solicitudesFiltradas.map((solicitud) => (
                  <tr key={solicitud.id}>
                    <td>
                      <strong>{solicitud.nombre} {solicitud.apellido}</strong>
                    </td>
                    <td>
                      <strong>{solicitud.telefono_contacto}</strong>
                      <small>{solicitud.email_contacto}</small>
                    </td>
                    <td>{solicitud.fecha_evento}</td>
                    <td>{solicitud.descripcion_solicitud}</td>
                    <td>
                      <span className={`estado-badge ${solicitud.estado}`}>
                        {estadoLabels[solicitud.estado] || solicitud.estado}
                      </span>
                    </td>
                    <td>
                      <div className="acciones-cell">
                        <button title="Editar" onClick={() => abrirEditarSolicitud(solicitud)}>
                          <i className="bi bi-pencil-square"></i>
                        </button>
                        <button title="En revisión" onClick={() => actualizarSolicitud(solicitud.id, { estado: "en_revision" })}>
                          <i className="bi bi-search"></i>
                        </button>
                        <button title="Aceptar" onClick={() => actualizarSolicitud(solicitud.id, { estado: "aceptada" })}>
                          <i className="bi bi-check-lg"></i>
                        </button>
                        <button title="Completar" onClick={() => actualizarSolicitud(solicitud.id, { estado: "completada" })}>
                          <i className="bi bi-check2-circle"></i>
                        </button>
                        {solicitud.estado === "aceptada" && (
                          <button title="Convertir en pedido especial" onClick={() => abrirConvertirPedido(solicitud)}>
                            <i className="bi bi-receipt-cutoff"></i>
                          </button>
                        )}
                        <button className="delete" title="Rechazar" onClick={() => rechazarSolicitud(solicitud.id)}>
                          <i className="bi bi-x-lg"></i>
                        </button>
                      </div>
                    </td>
                  </tr>
                  ))
                )}
              </tbody>
            </table>

            <footer className="table-footer">
              <span>Página {paginaActual} · Mostrando {solicitudesFiltradas.length} de {totalSolicitudes} solicitudes</span>
              <div className="paginations">
                <button
                  disabled={!paginaAnterior}
                  onClick={() => {
                    const nuevaPagina = Math.max(1, paginaActual - 1);
                    setPaginaActual(nuevaPagina);
                    cargarSolicitudes(nuevaPagina);
                  }}
                >
                  Anterior
                </button>
                <button
                  disabled={!paginaSiguiente}
                  onClick={() => {
                    const nuevaPagina = paginaActual + 1;
                    setPaginaActual(nuevaPagina);
                    cargarSolicitudes(nuevaPagina);
                  }}
                >
                  Siguiente
                </button>
              </div>
            </footer>
          </section>

          {mostrarFormulario && (
          <div className="modal-reserva-bg">
            <form className="modal-reserva" onSubmit={guardarSolicitud}>
              <h2>{modoModal === "crear" ? "Crear solicitud" : "Modificar solicitud"}</h2>

              <input
                type="text"
                placeholder="Nombre"
                value={formSolicitud.nombre}
                onChange={(e) => setFormSolicitud({ ...formSolicitud, nombre: e.target.value })}
                required
              />

              <input
                type="text"
                placeholder="Apellido"
                value={formSolicitud.apellido}
                onChange={(e) => setFormSolicitud({ ...formSolicitud, apellido: e.target.value })}
                required
              />

              <input
                type="date"
                value={formSolicitud.fecha_evento}
                onChange={(e) => setFormSolicitud({ ...formSolicitud, fecha_evento: e.target.value })}
                required
              />

              <input
                type="text"
                placeholder="Teléfono de contacto"
                value={formSolicitud.telefono_contacto}
                onChange={(e) => setFormSolicitud({ ...formSolicitud, telefono_contacto: e.target.value })}
                required
              />

              <input
                type="email"
                placeholder="Email de contacto"
                value={formSolicitud.email_contacto}
                onChange={(e) => setFormSolicitud({ ...formSolicitud, email_contacto: e.target.value })}
                required
              />

              <select
                value={formSolicitud.estado}
                onChange={(e) => setFormSolicitud({ ...formSolicitud, estado: e.target.value })}
              >
                {ESTADOS.map((estado) => (
                  <option key={estado} value={estado}>
                    {estadoLabels[estado]}
                  </option>
                ))}
              </select>

              <textarea
                placeholder="Descripción de la solicitud"
                value={formSolicitud.descripcion_solicitud}
                onChange={(e) => setFormSolicitud({ ...formSolicitud, descripcion_solicitud: e.target.value })}
                required
              />

              <div className="modal-actions">
                <button className="button-cancelar" type="button" onClick={() => setMostrarFormulario(false)}>
                  Cancelar
                </button>

                <button type="submit" disabled={guardando}>
                  {guardando ? "Guardando..." : "Guardar solicitud"}
                </button>
              </div>
            </form>
          </div>
          )}
          {solicitudPedido && (
          <div className="modal-reserva-bg">
            <form className="modal-reserva pedido-form-modal" onSubmit={convertirEnPedidoEspecial}>
              <h2>Convertir en pedido especial</h2>
              <p className="pedido-detalle-subtitle">
                {solicitudPedido.nombre} {solicitudPedido.apellido}
              </p>

              <input
                type="date"
                value={formPedidoEspecial.fecha_entrega}
                onChange={(e) => setFormPedidoEspecial({ ...formPedidoEspecial, fecha_entrega: e.target.value })}
                required
              />

              <div className="pedido-items-form">
                {formPedidoEspecial.items.map((item, index) => (
                  <div className="pedido-item-row" key={index}>
                    <input
                      type="text"
                      placeholder="Item"
                      value={item.nombre}
                      onChange={(e) => actualizarItemPedido(index, "nombre", e.target.value)}
                      required
                    />
                    <input
                      type="number"
                      min="1"
                      value={item.cantidad}
                      onChange={(e) => actualizarItemPedido(index, "cantidad", e.target.value)}
                      required
                    />
                    <input
                      type="number"
                      min="0"
                      value={item.precio_unitario}
                      onChange={(e) => actualizarItemPedido(index, "precio_unitario", e.target.value)}
                      required
                    />
                    <button type="button" className="delete" onClick={() => quitarItemPedido(index)}>
                      <i className="bi bi-trash"></i>
                    </button>
                  </div>
                ))}
                <button type="button" className="export-btn" onClick={agregarItemPedido}>
                  <i className="bi bi-plus-lg"></i>
                  Agregar item
                </button>
              </div>

              <div className="modal-actions">
                <button className="button-cancelar" type="button" onClick={() => setSolicitudPedido(null)}>
                  Cancelar
                </button>
                <button type="submit">Crear pedido</button>
              </div>
            </form>
          </div>
          )}
        </section>
      </main>
    </div>
  );
}
