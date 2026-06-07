import "bootstrap/dist/css/bootstrap.min.css";
import 'bootstrap-icons/font/bootstrap-icons.css';
import "../styles/dashboard.css";
import MainMenu from "../componentes/Main-menu";
import Card from "../componentes/card-metric";
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { authFetch } from "../api";
import { FaMotorcycle } from "react-icons/fa6";
import { AiOutlineShop } from "react-icons/ai";
import { TbShoppingBag } from "react-icons/tb";

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
  const [modalNotificacionesAbierto, setModalNotificacionesAbierto] = useState(false);
  const [notificaciones, setNotificaciones] = useState([]);
  const [notificacionesLoading, setNotificacionesLoading] = useState(false);
  const [notificacionesError, setNotificacionesError] = useState("");
  const [notificacionDetalle, setNotificacionDetalle] = useState(null);
  const [detalleLoading, setDetalleLoading] = useState(false);

  const actualizarContadorNotificaciones = (pendientes) => {
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
  };

  const fetchNotificaciones = async () => {
    setNotificacionesLoading(true);
    setNotificacionesError("");

    try {
      const response = await authFetch("/mi-restaurante/notificaciones/?leida=false", {
        cache: "no-store",
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result?.error || "No se pudieron cargar las notificaciones");
      }

      setNotificaciones(result.results || []);
      actualizarContadorNotificaciones(result.pendientes ?? 0);
    } catch (err) {
      setNotificaciones([]);
      setNotificacionesError(err.message || "No se pudieron cargar las notificaciones");
    } finally {
      setNotificacionesLoading(false);
    }
  };

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
      const detalleData = await detalleResponse.json();

      if (!detalleResponse.ok) {
        throw new Error(detalleData?.error || "No se pudo cargar el detalle");
      }

      const marcarResponse = await authFetch(
        `/mi-restaurante/notificaciones/${notificacionId}/marcar-leida/`,
        { method: "PATCH" }
      );
      const marcarData = await marcarResponse.json();

      if (!marcarResponse.ok) {
        throw new Error(marcarData?.error || "No se pudo marcar como leída");
      }

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
      const data = await response.json();

      if (!response.ok) return;

      setProductosClickeados(data || []);
    } catch {
      setProductosClickeados([]);
    }
  };

  const fetchUltimosPedidos = async () => {
    setUltimosPedidosLoading(true);
    setUltimosPedidosError("");

    try {
      const response = await authFetch("/dashboard/ultimos-pedidos/", {
        cache: "no-store",
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result?.error || "No se pudieron cargar los ultimos pedidos");
      }

      setUltimosPedidos(result || []);
    } catch (err) {
      setUltimosPedidos([]);
      setUltimosPedidosError(err.message || "No se pudieron cargar los ultimos pedidos");
    } finally {
      setUltimosPedidosLoading(false);
    }
  };

  useEffect(() => {
    const fetchRestaurante = async () => {
      try {
        const token = localStorage.getItem("access");

        if (!token) {
          navigate("/");
          return;
        }

        const response = await authFetch("/mi-restaurante/", {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("Error al cargar datos");
        }

        const result = await response.json();

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
        fetchClicks();
        fetchUltimosPedidos();
      } catch {
        setError("No se pudieron cargar los datos");
      } finally {
        setLoading(false);
      }
    };

    fetchRestaurante();
  }, [slug, navigate]);

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

  const iconoPedido = (tipoEntrega) => {
    if (tipoEntrega === "delivery") return <FaMotorcycle/>;
    if (tipoEntrega === "retiro_local") return <AiOutlineShop/>;
    if (tipoEntrega === "para_llevar") return <TbShoppingBag/>;
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
                <MainMenu />
                {/*header + body ---- falta*/}
                <section className="body-main1">
                    {cuentaInactiva && (
                        <div className="dashboard-inactive-banner">
                            <i className="bi bi-exclamation-triangle"></i>
                            <span>{mensajeCuentaInactiva}</span>
                        </div>
                    )}
                    <div className="header-logo-bienvenido"> 
                        <div className="div-header-logo">
                            <div className="bienvenidos">
                                <h5>¡Bienvenido, {usuario.username}!</h5>
                                <h1>{restaurante.nombre_empresa}</h1>
                                <p><i className="bi bi-calendar2-week"></i> Resumen de hoy, <span className="fecha">{hoy}</span></p>
                            </div>
                        </div>
                    </div>
                    <div className="contenido-body">
                        <div className="body-metric-notific">
                            <div className="metric">{/* FALTAN LAS METRICAS SACADA DE LAS BD */}
                                <Card
                                    icons = {"bi bi-fork-knife"}
                                    metrica={data?.resumen?.productos_disponibles ?? 0}
                                    titulo="Platos disponibles"
                                    btnto={`/carta-productos/${restaurante.slug}`}
                                />
                                <Card
                                    icons = {"bi bi-calendar2-check"}
                                    metrica={data?.resumen?.reservas_hoy ?? 0}
                                    titulo="Reservas para hoy"
                                    btnto={`/dashboard/${restaurante.slug}/reservas`}
                                />
                                <Card
                                    icons= {"bi bi-exclamation-circle"}
                                    metrica={data?.resumen?.productos_no_disponibles ?? 0}
                                    titulo="Platos no disponibles"
                                    btnto={`/carta-productos/${restaurante.slug}`}
                                />
                            </div>
                            <div className="notific">
                                <i className="bi bi-envelope-fill"></i>
                                <h5>{contadorNotificaciones}</h5>
                                <p>Notificaciones pendientes</p>
                                <button
                                  className="btn-ver-notificaciones"
                                  disabled={cuentaInactiva}
                                  title={cuentaInactiva ? "Cuenta inactiva" : undefined}
                                  onClick={abrirNotificaciones}
                                >
                                  Ver notificaciones <span><i className="bi bi-arrow-right-short"></i></span>
                                </button>
                            </div>
                            
                        </div>
                        <div className="body-ultimos-cliks">
                            <div className="div-ultimos-cambios">
                                <p><i className="bi bi-receipt-cutoff"></i> Últimos pedidos</p>
                                <div className="reports-cambios">
                                    {ultimosPedidosLoading ? (
                                      <p className="empty-text">Cargando últimos pedidos...</p>
                                    ) : ultimosPedidosError ? (
                                      <p className="empty-text">{ultimosPedidosError}</p>
                                    ) : ultimosPedidos.length === 0 ? (
                                      <p className="empty-text">Aún no hay pedidos recientes.</p>
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
                            <div className="clicks">
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
                             
                            </div>
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
