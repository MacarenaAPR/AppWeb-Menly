import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCallback } from "react";
import MainMenu from "../componentes/Main-menu";
import "../styles/configuracion.css";

import InfoRestaurante from "../componentes/configuraciones/info";
import UsuariosConfig from "../componentes/configuraciones/usuario";
import CategoriasConfig from "../componentes/configuraciones/categoria";
import MesasConfig from "../componentes/configuraciones/mesas";
import HorariosConfig from "../componentes/configuraciones/horarios";
import MetodoPago from "../componentes/configuraciones/metodos";
import NotificacionesConfig from "../componentes/configuraciones/notificaciones";
import Impresion from "../componentes/configuraciones/impresion";
import RespaldoSeguridad from "../componentes/configuraciones/respaldoyseguridad";
import IntegracionesConfig from "../componentes/configuraciones/integraciones";
import SistemaConfig from "../componentes/configuraciones/sistema";
import { authFetch } from "../api";
import { getRolActual, permisosPorRol } from "../utils/permisos";
export default function ConfiguracionRestaurante() {
  const [data, setData] = useState(null);
  const [seccionActiva, setSeccionActiva] = useState("info");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const navigate = useNavigate();

  const formatearHora = (hora) => {
    if (!hora) return "--:--";
    return String(hora).slice(0, 5);
  };

  const cargarConfiguracion = useCallback(async () => {
    try {
      setLoading(true);

      const token = localStorage.getItem("access");

      if (!token) {
        navigate("/");
        return;
      }

      const response = await authFetch("/mi-restaurante/configuracion/");

      if (!response.ok) {
        throw new Error("No se pudo cargar la configuración");
      }

      const result = await response.json();
      setData(result);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    cargarConfiguracion();
  }, [cargarConfiguracion]);

  if (loading) return <p>Cargando configuración...</p>;
  if (error) return <div className="alert alert-danger">{error}</div>;

  const restaurante = data.restaurante;
  const rol = data.usuario?.rol || restaurante?.rol || getRolActual();
  const permisos = permisosPorRol(rol);

  const menuConfig = [
    { id: "info", icon: "bi bi-info-circle", text: "Información del restaurante" },
    ...(permisos.isDueno ? [{ id: "usuarios", icon: "bi bi-person", text: "Usuarios y permisos" }] : []),
    { id: "categorias", icon: "bi bi-tag", text: "Categorías" },
    { id: "mesas", icon: "bi bi-table", text: "Mesas" },
    { id: "horarios", icon: "bi bi-clock", text: "Horarios de atención" },
    { id: "metodos", icon: "bi bi-credit-card", text: "Métodos de pago" },
    ...(permisos.isDueno ? [{ id: "notificaciones", icon: "bi bi-bell", text: "Notificaciones" }] : []),
    { id: "impresion", icon: "bi bi-printer", text: "Impresión" },
    { id: "seguridad", icon: "bi bi-shield-check", text: "Respaldo y seguridad" },
    ...(permisos.isDueno ? [{ id: "integraciones", icon: "bi bi-puzzle", text: "Integraciones" }] : []),
    ...(permisos.isDueno ? [{ id: "sistema", icon: "bi bi-display", text: "Sistema" }] : []),
  ];

  return (
    <div className="body">
      <main className="container-fluid" id="main">
        <MainMenu />

        <section className="config-page">
          <header className="config-header">
            <div>
              <h1>Configuraciones</h1>
              <p>Administra los ajustes de tu restaurante y del sistema.</p>
            </div>

            <div className="restaurante-mini">
              <i className="bi bi-shop"></i>
              <div>
                <small>Restaurante actual</small>
                <strong>{restaurante.nombre_empresa}</strong>
              </div>
              <i className="bi bi-chevron-down"></i>
            </div>
          </header>

          <div className="config-layout">
            <aside className="config-sidebar">
              {menuConfig.map((item) => (
                <button
                  key={item.id}
                  className={seccionActiva === item.id ? "active" : ""}
                  onClick={() => setSeccionActiva(item.id)}
                >
                  <i className={item.icon}></i>
                  {item.text}
                </button>
              ))}
            </aside>

            <section className="config-content">
                {seccionActiva === "info" && (
                <InfoRestaurante
                    restaurante={data.restaurante}
                    readOnly={!permisos.canEditConfigCritica}
                    onUpdate={(updated) =>
                    setData({
                        ...data,
                        restaurante: updated,
                    })
                    }
                />
                )}
                {seccionActiva === "usuarios" && <UsuariosConfig />}
                {seccionActiva === "categorias" && <CategoriasConfig />}
                {seccionActiva === "mesas" && <MesasConfig onUpdate={cargarConfiguracion} />}
                {seccionActiva === "horarios" && <HorariosConfig onUpdate={cargarConfiguracion} />}
                {seccionActiva === "metodos" && <MetodoPago onUpdate={cargarConfiguracion} />}
                {seccionActiva === "notificaciones" && <NotificacionesConfig />}
                {seccionActiva === "impresion" && <Impresion/>}
                {seccionActiva === "seguridad" && <RespaldoSeguridad />}
                {seccionActiva === "integraciones" && <IntegracionesConfig />}
                {seccionActiva === "sistema" && <SistemaConfig />}
              {seccionActiva === "info" && (
              <div className="config-bottom-grid">
                <div className="config-card horarios-summary-card">
                  <div className="card-title small">
                    <i className="bi bi-clock"></i>
                    <div>
                      <h2>Horarios de atención</h2>
                      <p>Administra los horarios de tu restaurante.</p>
                    </div>
                  </div>

                  <div className="config-list">
                    {data.horarios.length === 0 ? (
                      <p className="empty-text">No hay horarios registrados.</p>
                    ) : (
                    data.horarios.map((h) => (
                      <div className="config-row" key={h.id}>
                        <span>{h.dia_nombre}</span>
                        <p>
                          {h.cerrado
                            ? "Cerrado"
                            : `${formatearHora(h.hora_apertura)} - ${formatearHora(h.hora_cierre)}`}
                        </p>
                        <strong className={h.cerrado ? "status closed" : "status open"}>
                          {h.cerrado ? "Cerrado" : "Abierto"}
                        </strong>
                      </div>
                    ))
                    )}
                  </div>

                  <button className="btn-card-action" onClick={() => setSeccionActiva("horarios")}>
                    Editar horarios
                  </button>
                </div>

                <div className="config-card">
                  <div className="card-title small">
                    <i className="bi bi-credit-card"></i>
                    <div>
                      <h2>Métodos de pago</h2>
                      <p>Gestiona los métodos aceptados.</p>
                    </div>
                  </div>

                  <div className="config-list">
                    {data.metodos_pago.length === 0 ? (
                      <p className="empty-text">No hay métodos de pago registrados.</p>
                    ) : (
                    data.metodos_pago.map((m) => (
                      <div className="payment-row" key={m.id}>
                        <span>
                          <i className="bi bi-wallet2"></i>
                          {m.nombre}
                        </span>
                        <div className={m.activo ? "switch active" : "switch"}></div>
                      </div>
                    ))
                    )}
                  </div>

                  <button className="btn-card-action" onClick={() => setSeccionActiva("metodos")}>
                    Administrar métodos
                  </button>
                </div>

                <div className="config-card">
                  <div className="card-title small">
                    <i className="bi bi-grid-3x3-gap"></i>
                    <div>
                      <h2>Mesas</h2>
                      <p>Gestiona las mesas del restaurante.</p>
                    </div>
                  </div>

                  <div className="config-list">
                    {data.mesas.length === 0 ? (
                      <p className="empty-text">No hay mesas registradas.</p>
                    ) : (
                      data.mesas.map((mesa) => (
                        <div className="config-row" key={mesa.id}>
                          <span>Mesa {mesa.numero}</span>
                          <strong className={mesa.activa ? "status open" : "status closed"}>
                            {mesa.activa ? "Activa" : "Inactiva"}
                          </strong>
                        </div>
                      ))
                    )}
                  </div>

                  <button className="btn-card-action" onClick={() => setSeccionActiva("mesas")}>
                    Gestionar mesas
                  </button>
                </div>
              </div>
              )}

              <footer className="config-footer">
                <div>
                  <i className="bi bi-shield-check"></i>
                  <div>
                    <strong>Tu sistema está protegido y actualizado</strong>
                    <p>Último respaldo: revisa la sección Respaldo y seguridad</p>
                  </div>
                </div>

                <button onClick={() => setSeccionActiva("seguridad")}>
                  <i className="bi bi-cloud-arrow-up"></i>
                  Realizar respaldo ahora
                </button>
              </footer>
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}


