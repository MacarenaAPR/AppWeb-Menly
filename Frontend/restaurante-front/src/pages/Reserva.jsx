import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import "../styles/ReservasDashboard.css";
import MainMenu from "../componentes/Main-menu";
import { authFetch } from "../api";

export default function ReservasDashboard() {
    const [searchParams] = useSearchParams();
    const estadoUrl = searchParams.get("estado");
    const estadoInicial = ["pendiente", "confirmada", "rechazada", "cancelada"].includes(estadoUrl)
        ? estadoUrl
        : "todas";
    const [reservas, setReservas] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [paginaActual, setPaginaActual] = useState(1);
    const [totalReservas, setTotalReservas] = useState(0);
    const [paginaSiguiente, setPaginaSiguiente] = useState(null);
    const [paginaAnterior, setPaginaAnterior] = useState(null);

    const [ordenFecha, setOrdenFecha] = useState("asc");
    const [filtroEstado, setFiltroEstado] = useState(estadoInicial);
    const [filtroTurno, setFiltroTurno] = useState("todos");
    const [busqueda, setBusqueda] = useState("");
    const [filtroFecha, setFiltroFecha] = useState("todas");
    const [modoModal, setModoModal] = useState("crear");
    const [reservaEditando, setReservaEditando] = useState(null);

    const abrirEditarReserva = (reserva) => {
        setModoModal("editar");
        setReservaEditando(reserva);

        setFormReserva({
            nombre_cliente: reserva.nombre_cliente || "",
            telefono: reserva.telefono || "",
            email: reserva.email || "",
            fecha: reserva.fecha || "",
            hora: reserva.hora ? reserva.hora.slice(0, 5) : "",
            cantidad_personas: reserva.cantidad_personas || 1,
            mensaje: reserva.mensaje || "",
            mesa_asignada: reserva.mesa_asignada || "",
            observacion_admin: reserva.observacion_admin || "",
        });

        setMostrarFormulario(true);
    };

    const guardarReserva = async (e) => {
        e.preventDefault();
        setError("");

        if (modoModal === "crear") {
            await crearReservaManual(e);
            return;
        }

        const actualizado = await actualizarReserva(reservaEditando.id, {
            fecha: formReserva.fecha,
            hora: formReserva.hora ? formReserva.hora.slice(0, 5) : "",
            cantidad_personas: formReserva.cantidad_personas,
            mensaje: formReserva.mensaje,
            mesa_asignada: formReserva.mesa_asignada,
            observacion_admin: formReserva.observacion_admin,
        });

        if (!actualizado) return;

        setMostrarFormulario(false);
        setReservaEditando(null);
        setModoModal("crear");
    };

    const cargarReservas = useCallback(async (page = paginaActual) => {
        try {
        const response = await authFetch(`/mi-restaurante/reservas/?page=${page}`);

        const data = await response.json();
        setReservas(data.results || data);
        setTotalReservas(data.count ?? (Array.isArray(data) ? data.length : 0));
        setPaginaSiguiente(data.next || null);
        setPaginaAnterior(data.previous || null);
        } catch {
        setReservas([]);
        setTotalReservas(0);
        setPaginaSiguiente(null);
        setPaginaAnterior(null);
        } finally {
        setLoading(false);
        }
    }, [paginaActual]);

    useEffect(() => {
        cargarReservas();
    }, [cargarReservas]);

    const actualizarReserva = async (id, datos) => {
        try {
        const response = await authFetch(
            `/mi-restaurante/reservas/${id}/`,
            {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(datos),
            }
        );

        const data = await response.json();

        if (!response.ok) {
            setError(data.error || data.detail || "No se pudo actualizar la reserva");
            return false;
        }

        await cargarReservas();
        return true;
        } catch {
        setError("No se pudo actualizar la reserva");
        return false;
        }
    };

    const obtenerTurno = (hora) => {
        const h = Number(hora?.split(":")[0]);

        if (h >= 12 && h < 18) return "almuerzo";
        if (h >= 18 && h <= 23) return "cena";
        if (h >= 8 && h < 12) return "Desayuno";
        return "otro"; 
    };

    const reservasFiltradas = reservas.filter((reserva) => {
        const texto = `${reserva.nombre_cliente} ${reserva.telefono} ${reserva.email || ""}`.toLowerCase();

        const coincideBusqueda = texto.includes(busqueda.toLowerCase());

        const coincideEstado =
            filtroEstado === "todas"
                ? ["pendiente", "confirmada", "rechazada"].includes(reserva.estado)
                : reserva.estado === filtroEstado;

        const coincideTurno =
            filtroTurno === "todos" || obtenerTurno(reserva.hora) === filtroTurno;

        const hoy = new Date().toISOString().split("T")[0];

        const coincideFecha =
            filtroFecha === "todas" || reserva.fecha === hoy;

        

        return coincideBusqueda && coincideEstado && coincideTurno && coincideFecha;
    });
    const reservasOrdenadas = [...reservasFiltradas].sort((a, b) => {
            const fechaA = new Date(`${a.fecha}T${a.hora}`);
            const fechaB = new Date(`${b.fecha}T${b.hora}`);

            return ordenFecha === "desc" ? fechaA - fechaB : fechaB - fechaA;
            });

    const reservasHoy = reservas.filter((r) => {
        const hoy = new Date().toISOString().split("T")[0];
        return r.fecha === hoy;
    }).length;

    const pendientes = reservas.filter((r) => r.estado === "pendiente").length;

    const reservasVisiblesTodos = reservas.filter((r) =>
        ["pendiente", "confirmada", "rechazada"].includes(r.estado)
    );
    const reservasCanceladas = reservas.filter((r) => r.estado === "cancelada").length;

    const exportarCSV = () => {
        const encabezados = [
        "Cliente",
        "Email",
        "Telefono",
        "Fecha",
        "Hora",
        "Personas",
        "Mesa",
        "Estado",
        ];

        const filas = reservasFiltradas.map((r) => [
        r.nombre_cliente,
        r.email || "",
        r.telefono,
        r.fecha,
        r.hora,
        r.cantidad_personas,
        r.mesa_asignada || "",
        r.estado,
        ]);

        const csv = [encabezados, ...filas]
        .map((fila) => fila.map((dato) => `"${dato}"`).join(","))
        .join("\n");

        const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);

        const link = document.createElement("a");
        link.href = url;
        link.download = "reservas.csv";
        link.click();

        URL.revokeObjectURL(url);
    };
    const [mostrarFormulario, setMostrarFormulario] = useState(false);
    const [formReserva, setFormReserva] = useState({
        nombre_cliente: "",
        telefono: "",
        email: "",
        fecha: "",
        hora: "",
        cantidad_personas: 1,
        mensaje: "",
    });
    const crearReservaManual = async (e) => {
        e.preventDefault();

        try {
            const response = await authFetch(
            "/mi-restaurante/reservas/crear/",
            {
                method: "POST",
                headers: {
                "Content-Type": "application/json",
                },
                body: JSON.stringify(formReserva),
            }
            );

            const data = await response.json();

            if (!response.ok) {
            setError(data.error || "Error al crear reserva");
            return;
            }

            setMostrarFormulario(false);
            setError("");

            setFormReserva({
            nombre_cliente: "",
            telefono: "",
            email: "",
            fecha: "",
            hora: "",
            cantidad_personas: 1,
            mensaje: "",
            });

            cargarReservas();
        } catch {
            setError("Error al crear reserva");
        }
    };

  if (loading) {
    return <p className="reservas-loading">Cargando reservas...</p>;
  }

  return (
    <div className="body">
      <main className="container-fluid" id="main">
        <MainMenu />

        <section className="reservas-page">
            <header className="reservas-header">
                <h1>Reservas</h1>
                {error && <p className="reservas-error">{error}</p>}

                <div className="breadcrumb-reservas">
                <span>Inicio</span>
                <span>›</span>
                <strong>Reservas</strong>
                </div>
            </header>

            <section className="reservas-stats">
                <div className="reserva-stat-card">
                <div className="stat-icon">
                    <i className="bi bi-calendar-event"></i>
                </div>
                <div>
                    <h3>{reservasHoy}</h3>
                    <p>Reservas para hoy</p>
                </div>
                </div>

                <div className="reserva-stat-card">
                <div className="stat-icon">
                    <i className="bi bi-calendar-week"></i>
                </div>
                <div>
                    <h3>{reservas.length}</h3>
                    <p>Reservas totales</p>
                </div>
                </div>

                <div className="reserva-stat-card">
                <div className="stat-icon">
                    <i className="bi bi-people"></i>
                </div>
                <div>
                    <h3>{reservasCanceladas}</h3>
                    <p>Reservas canceladas</p>
                </div>
                </div>

                <div className="reserva-stat-card">
                <div className="stat-icon">
                    <i className="bi bi-clock"></i>
                </div>
                <div>
                    <h3>{pendientes}</h3>
                    <p>Pendientes por confirmar</p>
                </div>
                </div>
            </section>

            <section className="reservas-tools">
                <div className="filters-row">
                <select
                    value={filtroEstado}
                    onChange={(e) => setFiltroEstado(e.target.value)}
                >
                    <option value="todas">Todos los estados</option>
                    <option value="pendiente">Pendiente</option>
                    <option value="confirmada">Confirmada</option>
                    <option value="cancelada">Cancelada</option>
                    <option value="rechazada">Rechazada</option>
                </select>

                <select
                    value={filtroTurno}
                    onChange={(e) => setFiltroTurno(e.target.value)}
                >
                    <option value="todos">Todos los turnos</option>
                    <option value="desayuno">Desayuno</option>
                    <option value="almuerzo">Almuerzo</option>
                    <option value="cena">Cena</option>
                </select>

                <div className="search-box">
                    <i className="bi bi-search"></i>
                    <input
                    value={busqueda}
                    onChange={(e) => setBusqueda(e.target.value)}
                    placeholder="Buscar por nombre, teléfono o correo..."
                    />
                </div>

                <button className="export-btn" onClick={exportarCSV}>
                    <i className="bi bi-download"></i>
                    Exportar
                </button>
                </div>

                <div className="tabs-row">
                <button
                    className={`tab ${filtroFecha === "todas" && filtroEstado === "todas" ? "active" : ""}`}
                    onClick={() => {
                        setFiltroFecha("todas");
                        setFiltroEstado("todas");
                    }}
                    >
                    Todas ({reservasVisiblesTodos.length})
                    </button>

                <button
                    className={`tab ${filtroFecha === "hoy" ? "active" : ""}`}
                    onClick={() => {
                        setFiltroFecha("hoy");
                        setFiltroEstado("todas");
                    }}
                    >
                    Hoy ({reservasHoy})
                    </button>

                <button
                    className={`tab confirmadas ${filtroEstado === "confirmada" ? "active" : ""}`}
                    onClick={() => setFiltroEstado("confirmada")}
                >
                    Confirmadas ({reservas.filter((r) => r.estado === "confirmada").length})
                </button>

                <button
                    className={`tab pendientes ${filtroEstado === "pendiente" ? "active" : ""}`}
                    onClick={() => setFiltroEstado("pendiente")}
                >
                    Pendientes ({pendientes})
                </button>

                <button
                    className={`tab canceladas ${filtroEstado === "cancelada" ? "active" : ""}`}
                    onClick={() => setFiltroEstado("cancelada")}
                >
                    Canceladas ({reservas.filter((r) => r.estado === "cancelada").length})
                </button>
                <button
                    className="crear-reserva-btn"
                    onClick={() => {
                        setModoModal("crear");
                        setReservaEditando(null);
                        setFormReserva({
                        nombre_cliente: "",
                        telefono: "",
                        email: "",
                        fecha: "",
                        hora: "",
                        cantidad_personas: 1,
                        mensaje: "",
                        mesa_asignada: "",
                        observacion_admin: "",
                        });
                        setMostrarFormulario(true);
                    }}
                    >
                    <i className="bi bi-plus-lg"></i>
                    Crear reserva
                </button>
            </div>
            </section>

            <section className="reservas-table-card">
                <table className="reservas-table">
                <thead>
                    <tr>
                    <th
                        className="th-click"
                        onClick={() => setOrdenFecha(ordenFecha === "asc" ? "desc" : "asc")}
                        >
                        Fecha / Hora {ordenFecha === "asc" ? "↑" : "↓"}
                    </th>
                    <th>Cliente</th>
                    <th>Contacto</th>
                    <th>Personas</th>
                    <th>Mesa</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                    </tr>
                </thead>

                <tbody>
                    {reservasOrdenadas.length === 0 ? (
                    <tr>
                        <td colSpan="7">No hay reservas disponibles.</td>
                    </tr>
                    ) : (
                    reservasOrdenadas.map((reserva) => (
                    <tr key={reserva.id}>
                        <td>
                            <span className="fecha-cell">
                                <i className="bi bi-calendar-event"></i>
                                {new Date(`${reserva.fecha}T00:00:00`).toLocaleDateString("es-CL")}
                            </span>

                            <span className="hora-cell">
                                <i className="bi bi-clock"></i>
                                {reserva.hora}
                            </span>
                        </td>

                        <td>
                        <strong>{reserva.nombre_cliente}</strong>
                        <small>{reserva.email || "Sin correo"}</small>
                        </td>

                        <td>
                        <span className="contacto-cell">
                            <i className="bi bi-whatsapp"></i>
                            {reserva.telefono}
                        </span>
                        </td>

                        <td>
                        <span className="personas-cell">
                            <i className="bi bi-person"></i>
                            {reserva.cantidad_personas}
                        </span>
                        </td>

                        <td>
                        <input
                            className="mesa-input"
                            defaultValue={reserva.mesa_asignada || ""}
                            placeholder="Mesa"
                            onBlur={(e) =>
                            actualizarReserva(reserva.id, {
                                mesa_asignada: e.target.value,
                            })
                            }
                        />
                        </td>

                        <td>
                        <span className={`estado-badge ${reserva.estado}`}>
                            {reserva.estado}
                        </span>
                        </td>

                        <td>
                        <div className="acciones-cell">
                            <button
                                title="Editar"
                                onClick={() => abrirEditarReserva(reserva)}
                                >
                                <i className="bi bi-pencil-square"></i>
                            </button>
                            <button
                            title="Confirmar"
                            onClick={() =>
                                actualizarReserva(reserva.id, {
                                estado: "confirmada",
                                })
                            }
                            >
                            <i className="bi bi-check-lg"></i>
                            </button>

                            <button
                            title="Rechazar"
                            onClick={() =>
                                actualizarReserva(reserva.id, {
                                estado: "rechazada",
                                })
                            }
                            >
                            <i className="bi bi-x-lg"></i>
                            </button>

                            <button
                            className="delete"
                            title="Cancelar"
                            onClick={() =>
                                actualizarReserva(reserva.id, {
                                estado: "cancelada",
                                })
                            }
                            >
                            <i className="bi bi-trash"></i>
                            </button>
                        </div>
                        </td>
                    </tr>
                    ))
                    )}
                </tbody>
                </table>

                <footer className="table-footer">
                  <span>
                    Página {paginaActual} · Mostrando {reservasFiltradas.length} de {totalReservas} reservas
                  </span>
                  <div className="paginations">
                    <button
                      type="button"
                      disabled={!paginaAnterior}
                      onClick={() => setPaginaActual((page) => Math.max(1, page - 1))}
                    >
                      Anterior
                    </button>
                    <button
                      type="button"
                      disabled={!paginaSiguiente}
                      onClick={() => setPaginaActual((page) => page + 1)}
                    >
                      Siguiente
                    </button>
                  </div>
                </footer>
            </section>
        
        </section>
        {mostrarFormulario && (
            <div className="modal-reserva-bg">
                <form className="modal-reserva" onSubmit={guardarReserva}>
                    <h2>{modoModal === "crear" ? "Crear reserva" : "Modificar reserva"}</h2>

                    <input
                        type="text"
                        placeholder="Nombre cliente"
                        value={formReserva.nombre_cliente}
                        onChange={(e) =>
                        setFormReserva({ ...formReserva, nombre_cliente: e.target.value })
                        }
                        required
                        disabled={modoModal === "editar"}
                    />

                    <input
                        type="text"
                        placeholder="Teléfono"
                        value={formReserva.telefono}
                        onChange={(e) =>
                        setFormReserva({ ...formReserva, telefono: e.target.value })
                        }
                        required
                        disabled={modoModal === "editar"}
                    />

                    <input
                        type="email"
                        placeholder="Correo opcional"
                        value={formReserva.email}
                        onChange={(e) =>
                        setFormReserva({ ...formReserva, email: e.target.value })
                        }
                        disabled={modoModal === "editar"}
                    />

                    <input
                        type="date"
                        min={new Date().toISOString().split("T")[0]}
                        value={formReserva.fecha}
                        onChange={(e) =>
                            setFormReserva({ ...formReserva, fecha: e.target.value })
                        }
                        required
                    />

                    <input
                        type="time"
                        value={formReserva.hora}
                        onChange={(e) =>
                        setFormReserva({ ...formReserva, hora: e.target.value })
                        }
                        required
                    />

                    <div className="input-group-reserva">
                        <label>Cantidad de personas</label>

                        <input
                            type="number"
                            min="1"
                            placeholder="Ej: 2, 4, 6..."
                            value={formReserva.cantidad_personas}
                            onChange={(e) =>
                            setFormReserva({
                                ...formReserva,
                                cantidad_personas: e.target.value,
                            })
                            }
                            required
                        />
                    </div>

                    <textarea
                        placeholder="Mensaje u observación"
                        value={formReserva.mensaje}
                        onChange={(e) =>
                        setFormReserva({ ...formReserva, mensaje: e.target.value })
                        }
                    />

                    <div className="modal-actions">
                        <button  className="button-cancelar" type="button" onClick={() => setMostrarFormulario(false)}>
                        Cancelar
                        </button>

                        <button type="submit">
                            {modoModal === "crear" ? "Guardar reserva" : "Guardar cambios"}
                        </button>
                    </div>
                </form>
            </div>
            )}
      </main>
    </div>
  );
}
