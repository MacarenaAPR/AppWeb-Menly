import { useState } from "react";
import { buildMenuUrl } from "../../api";
import { formatearRolVisual } from "../../utils/permisos";


export default function SistemaConfig() {
  const [restaurante] = useState(() =>
    JSON.parse(localStorage.getItem("restaurante") || "null")
  );
  const [mensaje, setMensaje] = useState("");

  const copiarLinkMenu = () => {
    const link = buildMenuUrl(restaurante?.slug);

    if (!link) return;

    navigator.clipboard.writeText(link);
    setMensaje("Link copiado");
  };

  return (
    <div className="sistema-panel">
      <div className="usuarios-title">
        <i className="bi bi-gear"></i>
        <div>
          <h2>Sistema</h2>
          <p>Información general del restaurante dentro de la plataforma.</p>
        </div>
      </div>

      <section className="usuarios-card sistema-card">
        <h3>Datos del sistema</h3>

        <div className="sistema-grid">
          <div>
            <span>Restaurante</span>
            <strong>{restaurante?.nombre_empresa || "No disponible"}</strong>
          </div>

          <div>
            <span>Slug</span>
            <strong>{restaurante?.slug || "No disponible"}</strong>
          </div>

          <div>
            <span>Rol actual</span>
            <strong>{restaurante?.rol ? formatearRolVisual(restaurante.rol) : "No disponible"}</strong>
          </div>

          <div>
            <span>Estado</span>
            <strong>{restaurante?.activo ? "Activo" : "Inactivo"}</strong>
          </div>

          <div>
            <span>Plan</span>
            <strong>{restaurante?.plan?.nombre || "No disponible"}</strong>
          </div>

          <div>
            <span>Versión</span>
            <strong>Menuo v1.0</strong>
          </div>
        </div>

        <div className="sistema-actions">
          <button
            type="button"
            className="usuarios-save-btn"
            onClick={copiarLinkMenu}
          >
            Copiar link del menú
          </button>
          {mensaje && <p className="success-text">{mensaje}</p>}
        </div>
      </section>
    </div>
  );
}

