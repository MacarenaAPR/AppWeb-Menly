import { useCallback, useEffect, useState } from "react";
import { authFetch, limpiarSesionYRedirigir } from "../../api";

export default function RespaldoSeguridad() {
  const [restaurante] = useState(() =>
    JSON.parse(localStorage.getItem("restaurante") || "null")
  );
  const [loading, setLoading] = useState(false);
  const [loadingUltimo, setLoadingUltimo] = useState(true);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [ultimoRespaldo, setUltimoRespaldo] = useState(null);

  const descargarArchivo = (data, nombreArchivo) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = nombreArchivo;
    link.click();

    URL.revokeObjectURL(url);
  };

  const cargarUltimoRespaldo = useCallback(async () => {
    try {
      setLoadingUltimo(true);
      setError("");

      const response = await authFetch("/mi-restaurante/respaldos/ultimo/");
      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudo cargar el último respaldo.");
        return;
      }

      setUltimoRespaldo(data.ultimo_respaldo);
    } catch {
      setError("No se pudo cargar el último respaldo.");
    } finally {
      setLoadingUltimo(false);
    }
  }, []);

  useEffect(() => {
    cargarUltimoRespaldo();
  }, [cargarUltimoRespaldo]);

  const crearRespaldo = async () => {
    try {
      setLoading(true);
      setMensaje("");
      setError("");

      const response = await authFetch("/mi-restaurante/respaldos/", {
        method: "POST",
      });
      const respaldo = await response.json();

      if (!response.ok) {
        setError(respaldo.error || "No se pudo crear el respaldo.");
        return;
      }

      descargarArchivo(
        respaldo,
        `respaldo-${restaurante?.slug || "restaurante"}.json`
      );

      setUltimoRespaldo(respaldo);
      setMensaje("Respaldo creado correctamente.");
    } catch {
      setError("No se pudo crear el respaldo.");
    } finally {
      setLoading(false);
    }
  };

  const cerrarSesion = () => {
    limpiarSesionYRedirigir();
  };

  const diasDesdeUltimoRespaldo = ultimoRespaldo
    ? Math.floor((Date.now() - new Date(ultimoRespaldo.fecha_respaldo).getTime()) / (1000 * 60 * 60 * 24))
    : null;

  const mostrarAlerta14Dias = !ultimoRespaldo || diasDesdeUltimoRespaldo >= 14;

  const fechaUltimoRespaldo = ultimoRespaldo
    ? new Date(ultimoRespaldo.fecha_respaldo).toLocaleString("es-CL")
    : "Pendiente";

  return (
    <div className="respaldo-panel">
      <div className="usuarios-title">
        <i className="bi bi-shield-lock"></i>
        <div>
          <h2>Respaldo y seguridad</h2>
          <p>Crea una copia manual de tus datos y revisa la seguridad de acceso.</p>
        </div>
      </div>

      <section className="usuarios-card respaldo-card">
        <div className="respaldo-section">
          <h3>Respaldo de datos</h3>

          <div className="seguridad-grid">
            <div>
              <span>Último respaldo</span>
              <strong>{loadingUltimo ? "Cargando..." : fechaUltimoRespaldo}</strong>
            </div>
          </div>

          {mostrarAlerta14Dias && !loadingUltimo && (
            <p className="empty-text">
              Recomendación: crea un respaldo manual cada 14 días.
            </p>
          )}

          <p className="empty-text">
            Crea un respaldo manual en formato JSON con la información principal del restaurante.
          </p>

          <button
            type="button"
            className="usuarios-save-btn"
            onClick={crearRespaldo}
            disabled={loading}
          >
            {loading ? "Creando..." : "Crear respaldo"}
          </button>

          {mensaje && <p className="success-text">{mensaje}</p>}
          {error && <p className="empty-text">{error}</p>}
        </div>

        <div className="respaldo-divider"></div>

        <div className="respaldo-section">
          <h3>Seguridad de cuenta</h3>

          <div className="seguridad-grid">
            <div>
              <span>Restaurante</span>
              <strong>{restaurante?.nombre_empresa || "No disponible"}</strong>
            </div>

            <div>
              <span>Rol actual</span>
              <strong>{restaurante?.rol || "No disponible"}</strong>
            </div>

            <div>
              <span>Estado</span>
              <strong>Acceso protegido</strong>
            </div>
          </div>

          <button
            type="button"
            className="usuarios-delete-btn"
            onClick={cerrarSesion}
          >
            Cerrar sesión
          </button>
        </div>
      </section>
    </div>
  );
}
