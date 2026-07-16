import { useCallback, useEffect, useState } from "react";
import { authFetch } from "../../api";
import {
  activarWebPush,
  desactivarWebPush,
  obtenerEstadoWebPush,
} from "../../pushNotifications";


export default function NotificacionesConfig() {
  const [form, setForm] = useState({
    notificar_reservas: true,
    email_notificacion: "",
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pushEstado, setPushEstado] = useState("loading");
  const [pushProcesando, setPushProcesando] = useState(false);
  const [pushMensaje, setPushMensaje] = useState("");

  const cargarConfiguracion = useCallback(async () => {
    try {
      const response = await authFetch("/mi-restaurante/configuracion/");

      const data = await response.json();

      if (!response.ok) {
        setError("Error al cargar configuración");
        return;
      }

      setForm({
        notificar_reservas: data.notificar_reservas ?? true,
        email_notificacion: data.email_notificacion || "",
      });
    } catch {
      setError("Error al cargar configuración");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarConfiguracion();
  }, [cargarConfiguracion]);

  useEffect(() => {
    obtenerEstadoWebPush()
      .then(({ estado }) => setPushEstado(estado))
      .catch(() => setPushEstado("error"));
  }, []);

  const activarNotificacionesEquipo = async () => {
    setPushProcesando(true);
    setPushMensaje("");
    try {
      const { estado } = await activarWebPush();
      setPushEstado(estado);
      if (estado === "enabled") {
        setPushMensaje("Notificaciones activadas en este equipo.");
      }
    } catch (requestError) {
      setPushEstado("error");
      setPushMensaje(requestError.message || "No se pudieron activar las notificaciones.");
    } finally {
      setPushProcesando(false);
    }
  };

  const desactivarNotificacionesEquipo = async () => {
    setPushProcesando(true);
    setPushMensaje("");
    try {
      const { estado } = await desactivarWebPush();
      setPushEstado(estado);
      setPushMensaje("Notificaciones desactivadas en este equipo.");
    } catch (requestError) {
      setPushMensaje(requestError.message || "No se pudieron desactivar las notificaciones.");
    } finally {
      setPushProcesando(false);
    }
  };

  const textoEstadoPush = {
    loading: "Comprobando este equipo...",
    enabled: "Notificaciones activadas",
    disabled: "Notificaciones desactivadas",
    denied: "Permiso bloqueado en el navegador",
    unsupported: "Este navegador no es compatible",
    error: "No se pudo comprobar el estado de las notificaciones",
  }[pushEstado];

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    setForm({
      ...form,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const guardarConfiguracion = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const response = await authFetch("/mi-restaurante/configuracion/", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        throw new Error("No se pudo guardar");
      }

      setSuccess("Configuración guardada correctamente");
    } catch {
      setError("Error al guardar configuración");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p>Cargando configuración...</p>;

  return (
    <div className="horarios-panel">
      <div className="usuarios-title">
        <i className="bi bi-bell"></i>
        <div>
          <h2>Notificaciones</h2>
          <p>Configura cómo quieres recibir avisos de reservas.</p>
        </div>
      </div>

      <section className="usuarios-card">
        <h3>Preferencias</h3>

        {error && <p className="empty-text">{error}</p>}
        {success && <p className="success-text">{success}</p>}

        <form className="usuarios-form" onSubmit={guardarConfiguracion}>
          <label className="categorias-check">
            <input
              type="checkbox"
              name="notificar_reservas"
              checked={form.notificar_reservas}
              onChange={handleChange}
            />
            Recibir notificaciones de nuevas reservas
          </label>

          <label>
            Correo de notificación
            <input
              type="email"
              name="email_notificacion"
              value={form.email_notificacion}
              onChange={handleChange}
              placeholder="ejemplo@email.com"
            />
          </label>

          <div className="usuarios-edit-actions">
            <button
              type="submit"
              className="usuarios-save-btn"
              disabled={saving}
            >
              {saving ? "Guardando..." : "Guardar cambios"}
            </button>
          </div>
        </form>
      </section>

      <section className="usuarios-card">
        <h3>Notificaciones en este equipo</h3>
        <p>Recibe avisos de nuevos pedidos aunque Menly este minimizado.</p>
        <p className="empty-text">{textoEstadoPush}</p>
        {pushMensaje && <p className={pushEstado === "error" ? "empty-text" : "success-text"}>{pushMensaje}</p>}

        <div className="usuarios-edit-actions">
          {pushEstado === "enabled" ? (
            <button
              type="button"
              className="usuarios-save-btn"
              onClick={desactivarNotificacionesEquipo}
              disabled={pushProcesando}
            >
              {pushProcesando ? "Desactivando..." : "Desactivar notificaciones en este equipo"}
            </button>
          ) : (
            <button
              type="button"
              className="usuarios-save-btn"
              onClick={activarNotificacionesEquipo}
              disabled={pushProcesando || pushEstado === "loading" || pushEstado === "unsupported" || pushEstado === "denied"}
            >
              {pushProcesando ? "Activando..." : "Activar notificaciones"}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
