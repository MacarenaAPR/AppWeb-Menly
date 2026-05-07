import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/style-componentes.css";
import { useState } from "react";
import { authFetch } from "../api";
export default function CardsProductos({
  price,
  titulo,
  categoria,
  img,
  disponible,
  destacado,
  deleting,
  id,
  onDelete,
  onEdit,
  canManage = true,
}) {
  const [estado, setEstado] = useState(disponible);

  const handleChange = async () => {
    const nuevoEstado = !estado;

    try {
      const response = await authFetch(`/mi-restaurante/productos/${id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          disponible: nuevoEstado,
        }),
      });

      if (!response.ok) {
        throw new Error("No se pudo actualizar");
      }

      setEstado(nuevoEstado);
    } catch {
      return;
    }
  };

  const handleDeleteClick = async () => {
  if (!onDelete) {
    return;
  }

  await onDelete(id);
};

  return (
    <div className="card" id="card-producto">
      <div className="producto-img-wrap">
        {destacado && <span className="producto-destacado-badge">Destacado</span>}
        <img src={img} className="card-img-top" alt={titulo} />
      </div>

      <div className="card-body">
        <h5 className="titulo-text-card">{titulo}</h5>
        <p className="categoria-text-card">{categoria}</p>

        <h4 className="price-text-card">
          $ {price} <span>CLP</span>
        </h4>

        {canManage && (
        <div className="div-form-buttons">
          <div className="form-check form-switch">
            <label className="form-check-label">
              Disponible
            </label>

            <input
              className="form-check-input"
              type="checkbox"
              checked={estado}
              onChange={handleChange}
            />
          </div>

          <div className="div-buttons">
            <button type="button" onClick={() => onEdit(id)}>
              <i className="bi bi-pencil-square"></i>
            </button>

            <button
              type="button"
              className="button-delet"
              onClick={handleDeleteClick}
              disabled={deleting}
            >
              {deleting ? <i className="bi bi-hourglass-split"></i> : <i className="bi bi-trash3"></i>}
            </button>
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
