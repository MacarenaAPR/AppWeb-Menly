import "bootstrap/dist/css/bootstrap.min.css";
import 'bootstrap-icons/font/bootstrap-icons.css';
import "../styles/dashboard.css";
import MainMenu from "../componentes/Main-menu";
import Card from "../componentes/card-metric";
import CardReports from "../componentes/card-reportes";
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { authFetch } from "../api";

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

  const { usuario, restaurante, ultimas_actualizaciones } = data;
  const cuentaInactiva = data?.cuenta_inactiva || restaurante?.activo === false;
  const mensajeCuentaInactiva =
    data?.mensaje_cuenta || "Cuenta inactiva. Contacta al soporte de Menly para reactivar tu cuenta.";
  const cambiosVisibles =
    usuario?.rol === "admin"
      ? ultimas_actualizaciones?.slice(0, 5)
      : ultimas_actualizaciones;
  const suscripcion = data?.suscripcion;
  const mostrarAlertaSuscripcion =
    restaurante?.activo === true && suscripcion?.por_vencer === true;
  const mensajeSuscripcion = `Tu suscripción vence ${
    suscripcion?.dias_restantes === 0
      ? "hoy"
      : `en ${suscripcion?.dias_restantes} días`
  }. Recuerda regularizar tu pago para mantener activo el servicio. Si ya realizaste el pago, ignora este mensaje.`;

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
                                <h5>{data?.resumen?.reservas_pendientes ?? 0}</h5>
                                <p>Notificaciones pendientes</p>
                                <button
                                  className="btn-ver-notificaciones"
                                  disabled={cuentaInactiva}
                                  title={cuentaInactiva ? "Cuenta inactiva" : undefined}
                                  onClick={() => navigate(`/dashboard/${restaurante.slug}/reservas?estado=pendiente`)}
                                >
                                  Ver reservas <span><i className="bi bi-arrow-right-short"></i></span>
                                </button>
                            </div>
                            
                        </div>
                        <div className="body-ultimos-cliks">
                            <div className="div-ultimos-cambios">
                                <p><i className="bi bi-clock-history"></i> Últimos cambios</p>
                                <div className="reports-cambios">
                                    {cambiosVisibles?.length === 0 ? (
                                      <p className="empty-text">No hay cambios recientes.</p>
                                    ) : (
                                    cambiosVisibles?.slice(0,10).map((p) => (
                                        <CardReports
                                        key={p.id}
                                        fecha_cambio={new Date(p.fecha).toLocaleDateString("es-CL")}
                                        Estado={p.accion}
                                        Producto={p.producto}
                                        descripcion={p.descripcion}
                                        usuario={p.usuario}
                                       
                                        />
                                    ))
                                    )}
                                </div>
                                {usuario?.rol === "dueno" && (
                                <button className="btn-ver-historial" onClick={() => navigate("/historial")}>
                                    <p>Ver historial completo</p>
                                    <i className="bi bi-arrow-right-short"></i>
                                </button>
                                )}
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
    </div>
  ) 
  ;
}
