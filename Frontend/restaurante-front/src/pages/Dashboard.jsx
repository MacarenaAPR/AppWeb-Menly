import "bootstrap/dist/css/bootstrap.min.css";
import 'bootstrap-icons/font/bootstrap-icons.css';
import "../styles/dashboard.css";
import MainMenu from "../componentes/Main-menu";
import Card from "../componentes/card-metric";
import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { authFetch, readJsonResponse } from "../api";
import { tieneSesionAdmin } from "../session/adminSession";
import { permisosPorRol } from "../utils/permisos";
import { FaMotorcycle } from "react-icons/fa6";
import { AiOutlineShop } from "react-icons/ai";
import { TbShoppingBag } from "react-icons/tb";

const formatearMoneda = (valor = 0) => {
  const numero = Number(valor) || 0;
  return numero.toLocaleString("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  });
};

const DASHBOARD_REFRESH_MS = 20000;
const MAX_ULTIMOS_PEDIDOS = 10;

export default function Dashboard() {
    
    const hoy = new Date().toLocaleDateString("es-CL", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const { slug } = useParams();
  const navigate = useNavigate();
  
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  
  const [productosClickeados, setProductosClickeados] = useState([]);
  const [ultimosPedidos, setUltimosPedidos] = useState([]);
  const [ultimosPedidosLoading, setUltimosPedidosLoading] = useState(false);
  const [ultimosPedidosError, setUltimosPedidosError] = useState("");
  const [metricasPedidos, setMetricasPedidos] = useState(null);
  const [modalNotificacionesAbierto, setModalNotificacionesAbierto] = useState(false);
  const [notificaciones, setNotificaciones] = useState([]);
  const [notificacionesLoading, setNotificacionesLoading] = useState(false);
  const [notificacionesError, setNotificacionesError] = useState("");
  const [notificacionDetalle, setNotificacionDetalle] = useState(null);
  const [detalleLoading, setDetalleLoading] = useState(false);
  const [aperturaLoading, setAperturaLoading] = useState(false);
  const [aperturaError, setAperturaError] = useState("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const actualizarContadorNotificaciones = useCallback((pendientes) => {
    setData((prev) => {
      if (!prev) return prev;

      return {
        ...prev,
        resumen: {
          ...prev.resumen,
          notificaciones_pendientes: pendientes,
        },
      };
    });
  }, []);

  const fetchNotificaciones = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setNotificacionesLoading(true);
      setNotificacionesError("");
    }

    try {
      const response = await authFetch("/mi-restaurante/notificaciones/?leida=false", {
        cache: "no-store",
      });
      const result = await readJsonResponse(
        response,
        "/mi-restaurante/notificaciones/?leida=false",
        "No se pudieron cargar las notificaciones"
      );

      setNotificaciones(result.results || []);
      actualizarContadorNotificaciones(result.pendientes ?? 0);
    } catch (err) {
      if (!silent) {
        setNotificaciones([]);
        setNotificacionesError(err.message || "No se pudieron cargar las notificaciones");
      }
    } finally {
      if (!silent) {
        setNotificacionesLoading(false);
      }
    }
  }, [actualizarContadorNotificaciones]);

  const abrirNotificaciones = () => {
    setModalNotificacionesAbierto(true);
    setNotificacionDetalle(null);
    fetchNotificaciones();
  };

  const cerrarNotificaciones = () => {
    setModalNotificacionesAbierto(false);
    setNotificacionDetalle(null);
    setNotificacionesError("");
  };

  const verDetalleNotificacion = async (notificacionId) => {
    setDetalleLoading(true);
    setNotificacionesError("");

    try {
      const detalleResponse = await authFetch(`/mi-restaurante/notificaciones/${notificacionId}/`, {
        cache: "no-store",
      });
      const detalleData = await readJsonResponse(
        detalleResponse,
        `/mi-restaurante/notificaciones/${notificacionId}/`,
        "No se pudo cargar el detalle"
      );

      const marcarResponse = await authFetch(
        `/mi-restaurante/notificaciones/${notificacionId}/marcar-leida/`,
        { method: "PATCH" }
      );
      const marcarData = await readJsonResponse(
        marcarResponse,
        `/mi-restaurante/notificaciones/${notificacionId}/marcar-leida/`,
        "No se pudo marcar como leida"
      );

      setNotificacionDetalle(marcarData.notificacion || detalleData);
      setNotificaciones((prev) => prev.filter((item) => item.id !== notificacionId));
      actualizarContadorNotificaciones(marcarData.pendientes ?? 0);
    } catch (err) {
      setNotificacionesError(err.message || "No se pudo cargar el detalle");
    } finally {
      setDetalleLoading(false);
    }
  };

  const fetchClicks = async () => {
    try {
      const response = await authFetch("/mi-restaurante/productos-mas-clickeados/");
      const data = await readJsonResponse(
        response,
        "/mi-restaurante/productos-mas-clickeados/",
        "No se pudieron cargar los productos"
      );

      setProductosClickeados(data || []);
    } catch {
      setProductosClickeados([]);
    }
  };

  const fetchUltimosPedidos = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setUltimosPedidosLoading(true);
      setUltimosPedidosError("");
    }

    try {
      const response = await authFetch("/dashboard/ultimos-pedidos/", {
        cache: "no-store",
      });
      const result = await readJsonResponse(
        response,
        "/dashboard/ultimos-pedidos/",
        "No se pudieron cargar los datos"
      );

      setUltimosPedidos((result || []).slice(0, MAX_ULTIMOS_PEDIDOS));
    } catch (err) {
      if (!silent) {
        setUltimosPedidos([]);
        setUltimosPedidosError(err.message || "No se pudieron cargar los datos");
      }
    } finally {
      if (!silent) {
        setUltimosPedidosLoading(false);
      }
    }
  }, []);

  const fetchMetricasPedidos = useCallback(async ({ silent = false } = {}) => {
    try {
      const response = await authFetch("/mi-restaurante/metricas/resumen/", {
        cache: "no-store",
      });
      const result = await readJsonResponse(
        response,
        "/mi-restaurante/metricas/resumen/",
        "No se pudieron cargar los datos"
      );

      setMetricasPedidos(result);
    } catch (err) {
      console.error("/mi-restaurante/metricas/resumen/", err);
      if (!silent) {
        setMetricasPedidos(null);
      }
    }
  }, []);

  useEffect(() => {
    const fetchRestaurante = async () => {
      try {
        if (!tieneSesionAdmin()) {
          navigate("/");
          return;
        }

        const response = await authFetch("/mi-restaurante/", {
          cache: "no-store",
        });

        const result = await readJsonResponse(
          response,
          "/mi-restaurante/",
          "Error al cargar datos"
        );

        if (slug !== result.restaurante.slug) {
          navigate(`/dashboard/${result.restaurante.slug}`, { replace: true });
          return;
        }

        setData(result);
        localStorage.setItem(
          "restaurante",
          JSON.stringify({
            ...result.restaurante,
            rol: result.usuario?.rol,
          })
        );
        const esEmpleado = permisosPorRol(result.usuario?.rol).isEmpleado;

        fetchClicks();

        if (!esEmpleado) {
          fetchMetricasPedidos();
        }
        fetchUltimosPedidos();
      } catch {
        setError("No se pudieron cargar los datos");
      } finally {
        setLoading(false);
      }
    };

    fetchRestaurante();
  }, [slug, navigate, fetchUltimosPedidos, fetchMetricasPedidos]);

  useEffect(() => {
    if (!data) return undefined;

    const intervalId = window.setInterval(() => {
      fetchUltimosPedidos({ silent: true });
      if (!permisosPorRol(data.usuario?.rol).isEmpleado) {
        fetchMetricasPedidos({ silent: true });
      }
      fetchNotificaciones({ silent: true });
    }, DASHBOARD_REFRESH_MS);

    return () => window.clearInterval(intervalId);
  }, [data, fetchUltimosPedidos, fetchMetricasPedidos, fetchNotificaciones]);

  if (loading) {
    return <p>Cargando dashboard...</p>;
  }

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  if (!data) {
    return <p>No hay datos disponibles</p>;
  }

  const { usuario, restaurante } = data;
  const esEmpleado = permisosPorRol(usuario?.rol).isEmpleado;
  const cuentaInactiva = data?.cuenta_inactiva || restaurante?.activo === false;
  const mensajeCuentaInactiva =
    data?.mensaje_cuenta || "Cuenta inactiva. Contacta al soporte de Menly para reactivar tu cuenta.";
  const suscripcion = data?.suscripcion;
  const mostrarAlertaSuscripcion =
    restaurante?.activo === true && suscripcion?.por_vencer === true;
  const mensajeSuscripcion = `Tu suscripción vence ${
    suscripcion?.dias_restantes === 0
      ? "hoy"
      : `en ${suscripcion?.dias_restantes} días`
  }. Recuerda regularizar tu pago para mantener activo el servicio. Si ya realizaste el pago, ignora este mensaje.`;
  const contadorNotificaciones = data?.resumen?.notificaciones_pendientes ?? 0;
  const ventaTotalMes = metricasPedidos?.ventas?.venta_real_mes ?? 0;
  const tiendaAbierta = restaurante?.abierto === true;

  const cambiarEstadoApertura = async () => {
    if (!restaurante || aperturaLoading) return;

    const siguienteEstado = !tiendaAbierta;
    setAperturaLoading(true);
    setAperturaError("");

    try {
      const response = await authFetch("/mi-restaurante/estado-apertura/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ abierto: siguienteEstado }),
      });
      const result = await readJsonResponse(
        response,
        "/mi-restaurante/estado-apertura/",
        "No se pudo cambiar el estado de la tienda"
      );

      setData((prev) => {
        if (!prev) return prev;
        const restauranteActualizado = {
          ...prev.restaurante,
          abierto: result.abierto,
          abierto_ahora: result.abierto_ahora,
        };

        localStorage.setItem("restaurante", JSON.stringify(restauranteActualizado));

        return {
          ...prev,
          restaurante: restauranteActualizado,
        };
      });
    } catch (err) {
      setAperturaError(err.message || "No se pudo cambiar el estado de la tienda");
    } finally {
      setAperturaLoading(false);
    }
  };

  const iconoPedido = (tipoEntrega) => {
    if (tipoEntrega === "delivery") return <FaMotorcycle/>;
    if (tipoEntrega === "retiro_local","retiro") return <AiOutlineShop/>;
    if (tipoEntrega === "para_llevar","llevar") return <TbShoppingBag/>;
    return "bi bi-receipt";
  };

  const formatearFecha = (fecha) =>
    fecha
      ? new Date(fecha).toLocaleString("es-CL", {
          dateStyle: "medium",
          timeStyle: "short",
        })
      : "Sin fecha";

  const renderDetalleNotificacion = () => {
    const detalle = notificacionDetalle?.detalle;

    if (!detalle) {
      return <p className="notificaciones-empty">No se encontró el detalle asociado.</p>;
    }

    if (notificacionDetalle.tipo === "reserva") {
      return (
        <div className="notificacion-detalle-grid">
          <span>Cliente</span><strong>{detalle.nombre_cliente}</strong>
          <span>Fecha</span><strong>{detalle.fecha} {detalle.hora}</strong>
          <span>Personas</span><strong>{detalle.cantidad_personas}</strong>
          <span>Teléfono</span><strong>{detalle.telefono}</strong>
          <span>Email</span><strong>{detalle.email || "No informado"}</strong>
          <span>Mensaje</span><strong>{detalle.mensaje || "Sin mensaje"}</strong>
          <span>Estado</span><strong>{detalle.estado}</strong>
        </div>
      );
    }

    if (notificacionDetalle.tipo === "pedido") {
      const productos = detalle.productos_snapshot || detalle.items || [];
      const totalItems = productos.reduce(
        (total, item) => total + Number(item?.cantidad || 0),
        0
      );

      return (
        <div className="notificacion-detalle-grid">
          <span>N° pedido</span><strong>#{detalle.numero_pedido}</strong>
          <span>Cliente</span><strong>{detalle.nombre_cliente}</strong>
          <span>Teléfono</span><strong>{detalle.telefono_cliente}</strong>
          <span>Total</span><strong>{formatearMoneda(detalle.total)}</strong>
          <span>Productos</span><strong>{totalItems} productos</strong>
          <span>Estado</span><strong>{detalle.estado_display || detalle.estado}</strong>
        </div>
      );
    }

    return (
      <div className="notificacion-detalle-grid">
        <span>Cliente</span><strong>{detalle.nombre} {detalle.apellido}</strong>
        <span>Fecha evento</span><strong>{detalle.fecha_evento}</strong>
        <span>Teléfono</span><strong>{detalle.telefono_contacto}</strong>
        <span>Email</span><strong>{detalle.email_contacto}</strong>
        <span>Descripción</span><strong>{detalle.descripcion_solicitud}</strong>
        <span>Estado</span><strong>{detalle.estado}</strong>
      </div>
    );
  };

  return (
        <div className="body">
            <main className="container-fluid" id="main">
                {/*MENU */}
                <MainMenu
                  mobileMenuOpen={mobileMenuOpen}
                  onMobileMenuOpenChange={setMobileMenuOpen}
                />
                {/*header + body ---- falta*/}
                <section className="body-main1">
                    {cuentaInactiva && (
                        <div className="dashboard-inactive-banner">
                            <i className="bi bi-exclamation-triangle"></i>
                            <span>{mensajeCuentaInactiva}</span>
                        </div>
                    )}
                    <button
                      className={`notificaciones-burbuja ${mobileMenuOpen ? "is-hidden-by-mobile-menu" : ""}`}
                      type="button"
                      disabled={cuentaInactiva}
                      title={cuentaInactiva ? "Cuenta inactiva" : "Ver notificaciones"}
                      onClick={abrirNotificaciones}
                    >
                      <span className="notificaciones-burbuja-icon">
                        <i className="bi bi-envelope-fill"></i>
                      </span>
                      <span className="notificaciones-burbuja-text">Notificaciones</span>
                      <strong>{contadorNotificaciones}</strong>
                    </button>
                    <div className="header-logo-bienvenido"> 
                        <div className="div-header-logo">
                            <div className="bienvenidos">
                                <h5>¡Bienvenido, {usuario.username}!</h5>
                                <h1>{restaurante.nombre_empresa}</h1>
                                <div className="dashboard-store-status">
                                  <span className={tiendaAbierta ? "is-open" : "is-closed"}>
                                    {tiendaAbierta ? "Tienda abierta" : "Tienda cerrada"}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={cambiarEstadoApertura}
                                    disabled={cuentaInactiva || aperturaLoading}
                                  >
                                    {aperturaLoading
                                      ? "Actualizando..."
                                      : tiendaAbierta
                                        ? "Cerrar tienda"
                                        : "Abrir tienda"}
                                  </button>
                                </div>
                                {aperturaError && <small className="dashboard-store-error">{aperturaError}</small>}
                                <p><i className="bi bi-calendar2-week"></i> Resumen de hoy, <span className="fecha">{hoy}</span></p>
                            </div>
                        </div>
                    </div>
                    <div className="contenido-body">
                        {!esEmpleado && <div className="body-metric-notific">
                            <div className="metric">
                                <div className="card-metrics dashboard-platos-card">
                                  <div className="cards-icon-text">
                                    <div className="icon-circle">
                                      <svg xmlns="http://www.w3.org/2000/svg" width="65" height="65" viewBox="0 0 65 65" fill="none">
                                        <circle cx="32.2581" cy="32.2581" r="32.2581" fill="url(#paint_dashboard_platos)" />
                                        <defs>
                                          <linearGradient id="paint_dashboard_platos" x1="31.828" y1="-5.16129" x2="32.2581" y2="64.5161" gradientUnits="userSpaceOnUse">
                                            <stop stopColor="#F8761D" />
                                            <stop offset="0.9999" stopColor="#D44D29" />
                                          </linearGradient>
                                        </defs>
                                      </svg>
                                      <i className="bi bi-fork-knife"></i>
                                    </div>
                                    <div className="div-text-metric">
                                      <h1>{data?.resumen?.productos_disponibles ?? 0}</h1>
                                      <p>Platos</p>
                                      <div className="dashboard-platos-detail">
                                        <span>Disponibles: {data?.resumen?.productos_disponibles ?? 0}</span>
                                        <span>No disponibles: {data?.resumen?.productos_no_disponibles ?? 0}</span>
                                      </div>
                                    </div>
                                  </div>
                                  <button
                                    className="Button-detalles"
                                    type="button"
                                    onClick={() => navigate(`/carta-productos/${restaurante.slug}`)}
                                  >
                                    <p>Ver carta</p>
                                  </button>
                                </div>
                                <Card
                                    icons = {"bi bi-calendar2-check"}
                                    metrica={data?.resumen?.reservas_hoy ?? 0}
                                    titulo="Reservas para hoy"
                                    btnto={`/dashboard/${restaurante.slug}/reservas`}
                                />
                                <Card
                                    icons = {"bi bi-cash-stack"}
                                    metrica={formatearMoneda(ventaTotalMes)}
                                    titulo="Venta total del mes"
                                    btnto={`/dashboard/${restaurante.slug}/pedidos`}
                                />
                            </div>
                            
                        </div>}
                        <div className={esEmpleado ? "dashboard-empleado-grid" : "body-ultimos-cliks"}>
                            <div className="div-ultimos-cambios">
                                <p><i className="bi bi-receipt-cutoff"></i> Últimos pedidos</p>
                                <div className="reports-cambios">
                                    {ultimosPedidosLoading ? (
                                      <p className="empty-text">Cargando últimos pedidos...</p>
                                    ) : ultimosPedidosError ? (
                                      <p className="empty-text">{ultimosPedidosError}</p>
                                    ) : ultimosPedidos.length === 0 ? (
                                      <p className="empty-text">No hay pedidos registrados hoy.</p>
                                    ) : (
                                      ultimosPedidos.map((pedido) => (
                                        <article key={pedido.id} className="ultimo-pedido-item">
                                          <div className="ultimo-pedido-icon">
                                            {iconoPedido(pedido.tipo_entrega)}
                                          </div>
                                          <div className="ultimo-pedido-info">
                                            <strong>Pedido #{pedido.numero_pedido}</strong>
                                            <span>{pedido.nombre_cliente}</span>
                                          </div>
                                          <time>{pedido.hora_formateada}</time>
                                        </article>
                                      ))
                                    )}
                                </div>
                                <button className="btn-ver-historial" onClick={() => navigate(`/dashboard/${restaurante.slug}/pedidos`)}>
                                    <p>Ver todos los pedidos</p>
                                    <i className="bi bi-arrow-right-short"></i>
                                </button>
                            </div>
                            {esEmpleado ? (
                              <aside className="dashboard-empleado-operacion">
                                <section className="dashboard-empleado-disponibilidad">
                                  <div className="dashboard-empleado-operacion-title">
                                    <i className="bi bi-fork-knife"></i>
                                    <p>Estado de productos</p>
                                  </div>
                                  <div className="dashboard-empleado-disponibilidad-grid">
                                    <div>
                                      <span>Disponibles</span>
                                      <strong>{data?.resumen?.productos_disponibles ?? 0}</strong>
                                    </div>
                                    <div>
                                      <span>No disponibles</span>
                                      <strong>{data?.resumen?.productos_no_disponibles ?? 0}</strong>
                                    </div>
                                  </div>
                                </section>

                                <div className="clicks">
                                  <p>
                                    <i className="bi bi-fork-knife"></i> Productos más clickeados
                                  </p>
                                  <div className="div-clicks">
                                    {productosClickeados.length === 0 ? (
                                      <p className="empty-text">Sin datos aún</p>
                                    ) : (
                                      productosClickeados.slice(0, 5).map((p, i) => (
                                        <div key={p.id} className="click-item">
                                          <span className="click-rank">{i + 1}</span>
                                          <div className="click-img">
                                            {p.imagen ? (
                                              <img src={p.imagen} alt={p.nombre} />
                                            ) : (
                                              <i className="bi bi-fork-knife"></i>
                                            )}
                                          </div>
                                          <div className="click-info">
                                            <strong>{p.nombre}</strong>
                                            <p>{p.categoria}</p>
                                          </div>
                                          <div className="click-total">
                                            <strong>{p.clicks}</strong>
                                            <span>Clicks</span>
                                          </div>
                                        </div>
                                      ))
                                    )}
                                  </div>
                                </div>
                              </aside>
                            ) : <div className="clicks">
                              <p>
                                <i className="bi bi-fork-knife"></i> Platos más clickeados
                              </p>
                              <div className="div-clicks">
                                {productosClickeados.length === 0 ? (
                                  <p className="empty-text">Sin datos aún</p>
                                ) : (
                                  productosClickeados.slice(0, 5).map((p, i) => (
                                    <div key={p.id} className="click-item">
                                      
                                      {/* ranking */}
                                      <span className="click-rank">{i + 1}</span>

                                      {/* imagen */}
                                      <div className="click-img">
                                        {p.imagen ? (
                                          <img src={p.imagen} alt={p.nombre} />
                                        ) : (
                                          <i className="bi bi-fork-knife"></i>
                                        )}
                                      </div>

                                      {/* info */}
                                      <div className="click-info">
                                        <strong>{p.nombre}</strong>
                                        <p>{p.categoria}</p>
                                      </div>

                                      {/* clicks */}
                                      <div className="click-total">
                                        <strong>{p.clicks}</strong>
                                        <span>Clicks</span>
                                      </div>

                                    </div>
                                  ))
                                )}
                              </div>
                             
                            </div>}
                        </div>
                    </div>
                </section>

            </main>
            {cuentaInactiva && (
              <div className="dashboard-subscription-alert is-expired">
                <i className="bi bi-exclamation-triangle"></i>
                <span>{mensajeCuentaInactiva}</span>
              </div>
            )}
            {mostrarAlertaSuscripcion && (
              <div className="dashboard-subscription-alert is-warning">
                <i className="bi bi-info-circle"></i>
                <span>{mensajeSuscripcion}</span>
              </div>
            )}
            {modalNotificacionesAbierto && (
              <div className="notificaciones-modal-backdrop" role="dialog" aria-modal="true">
                <div className="notificaciones-modal">
                  <div className="notificaciones-modal-header">
                    <div>
                      <p>Centro de notificaciones</p>
                      <h2>
                        {notificacionDetalle ? "Detalle" : `${contadorNotificaciones} pendientes`}
                      </h2>
                    </div>
                    <button
                      type="button"
                      className="notificaciones-icon-btn"
                      onClick={cerrarNotificaciones}
                      aria-label="Cerrar"
                    >
                      <i className="bi bi-x-lg"></i>
                    </button>
                  </div>

                  {notificacionesError && (
                    <div className="notificaciones-error">{notificacionesError}</div>
                  )}

                  {notificacionDetalle ? (
                    <div className="notificacion-detalle">
                      <button
                        type="button"
                        className="notificaciones-volver"
                        onClick={() => setNotificacionDetalle(null)}
                      >
                        <i className="bi bi-arrow-left-short"></i>
                        Volver al listado
                      </button>
                      <span className="notificacion-tipo">{notificacionDetalle.tipo_display}</span>
                      <h3>{notificacionDetalle.titulo}</h3>
                      <p>{notificacionDetalle.mensaje}</p>
                      <small>{formatearFecha(notificacionDetalle.fecha_creacion)}</small>
                      {renderDetalleNotificacion()}
                    </div>
                  ) : (
                    <div className="notificaciones-lista">
                      {notificacionesLoading ? (
                        <p className="notificaciones-empty">Cargando notificaciones...</p>
                      ) : notificaciones.length === 0 ? (
                        <p className="notificaciones-empty">No hay notificaciones pendientes.</p>
                      ) : (
                        notificaciones.map((notificacion) => (
                          <article key={notificacion.id} className="notificacion-item">
                            <div>
                              <span className="notificacion-tipo">{notificacion.tipo_display}</span>
                              <h3>{notificacion.titulo}</h3>
                              <p>{notificacion.mensaje}</p>
                              <small>{formatearFecha(notificacion.fecha_creacion)}</small>
                            </div>
                            <button
                              type="button"
                              className="notificacion-ver-mas"
                              disabled={detalleLoading}
                              onClick={() => verDetalleNotificacion(notificacion.id)}
                            >
                              Ver más
                            </button>
                          </article>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
    </div>
  ) 
  ;
}
