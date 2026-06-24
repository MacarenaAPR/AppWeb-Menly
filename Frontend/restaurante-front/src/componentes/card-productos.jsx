import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/style-componentes.css";
import { useState } from "react";
import { authFetch } from "../api";
export default function CardsProductos({
  price,
  titulo,
  categoria,
  descripcion,
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
  const [estadoDestacado, setEstadoDestacado] = useState(destacado);

  const actualizarEstadoProducto = async (campo, valor) => {
    const estadoAnterior = campo === "disponible" ? estado : estadoDestacado;

    if (campo === "disponible") {
      setEstado(valor);
    } else {
      setEstadoDestacado(valor);
    }

    try {
      const response = await authFetch(`/mi-restaurante/productos/${id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          [campo]: valor,
        }),
      });

      if (!response.ok) {
        throw new Error("No se pudo actualizar");
      }
    } catch {
      if (campo === "disponible") {
        setEstado(estadoAnterior);
      } else {
        setEstadoDestacado(estadoAnterior);
      }
      return;
    }
  };

  const handleDisponibleChange = () => {
    actualizarEstadoProducto("disponible", !estado);
  };

  const handleDestacadoChange = () => {
    actualizarEstadoProducto("destacado", !estadoDestacado);
  };

  const handleDeleteClick = async () => {
  if (!onDelete) {
    return;
  }

  await onDelete(id);
};

  return (
    <div className="card" id="card-producto">
      <div className="producto-table-cell producto-cell-main">
        <div className="producto-img-wrap">
          {estadoDestacado && <span className="producto-destacado-badge">Destacado</span>}
          <img src={img} className="card-img-top" alt={titulo} />
        </div>

        <div className="producto-main-text">
          <h5 className="titulo-text-card">{titulo}</h5>
          <p className="producto-description-text">{descripcion || categoria || "Sin descripción"}</p>
        </div>
      </div>

      <div className="card-body producto-table-cell producto-cell-category">
        <p className="categoria-text-card">{categoria}</p>
      </div>

      <div className="producto-table-cell producto-cell-price">
        <h4 className="price-text-card">
          $ {price} <span>CLP</span>
        </h4>
      </div>

      {canManage && (
        <>
          <div className="producto-table-cell producto-cell-switch">
            <div className="form-check form-switch producto-switch">
              <label className="form-check-label">Disponible</label>

              <input
                className="form-check-input"
                type="checkbox"
                checked={estado}
                onChange={handleDisponibleChange}
              />
            </div>
          </div>

          <div className="producto-table-cell producto-cell-switch">
            <div className="form-check form-switch producto-switch">
              <label className="form-check-label">Destacado</label>

              <input
                className="form-check-input"
                type="checkbox"
                checked={estadoDestacado}
                onChange={handleDestacadoChange}
              />
            </div>
          </div>

          <div className="producto-table-cell div-buttons producto-cell-actions">
            <button className="btn-pencil" type="button" onClick={() => onEdit(id)}>
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
        </>
      )}
    </div>
  );
}
