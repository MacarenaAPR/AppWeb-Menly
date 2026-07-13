import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/style-componentes.css";
import { useState } from "react";
import { authFetch } from "../api";

const formatearPrecioClp = (valor) =>
  new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(Number(valor || 0));

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
  onDestacadoChange,
  variantesCount = 0,
  isListView = false,
  isCardsView = false,
  canManage = true,
  canToggleAvailability = canManage,
  isEmployeeView = false,
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

  const handleDestacadoChange = async () => {
    const nuevoEstadoDestacado = !estadoDestacado;
    const estadoAnterior = estadoDestacado;

    setEstadoDestacado(nuevoEstadoDestacado);

    try {
      const response = await authFetch(`/mi-restaurante/productos/${id}/actualizar/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          destacado: nuevoEstadoDestacado,
        }),
      });

      if (!response.ok) {
        throw new Error("No se pudo actualizar");
      }

      onDestacadoChange?.(id, nuevoEstadoDestacado);
    } catch {
      setEstadoDestacado(estadoAnterior);
      return;
    }
  };

  const handleDeleteClick = async () => {
  if (!onDelete) {
    return;
  }

  await onDelete(id);
};

  if (isEmployeeView) {
    return (
      <article className="producto-empleado-row">
        <div className="producto-empleado-image">
          {img ? (
            <img src={img} alt={titulo} />
          ) : (
            <span className="producto-img-placeholder" aria-hidden="true">
              <i className="bi bi-image"></i>
            </span>
          )}
        </div>

        <strong className="producto-empleado-name">{titulo}</strong>
        <span className="producto-empleado-category">{categoria || "Sin categoría"}</span>
        <strong className="producto-empleado-price">{formatearPrecioClp(price)}</strong>

        {canToggleAvailability && (
          <label className="form-switch producto-empleado-available" htmlFor={`producto-empleado-disponible-${id}`}>
            <span>{estado ? "Disponible" : "No disponible"}</span>
            <input
              id={`producto-empleado-disponible-${id}`}
              className="form-check-input"
              type="checkbox"
              role="switch"
              checked={estado}
              onChange={handleDisponibleChange}
            />
          </label>
        )}
      </article>
    );
  }

  return (
    <>
      {isListView && (
        <article className="producto-mobile-list-row">
          <div className="producto-mobile-list-top">
            <strong className="producto-mobile-list-name">{titulo}</strong>
            <strong className="producto-mobile-list-price">{formatearPrecioClp(price)}</strong>
          </div>

          <div className="producto-mobile-list-bottom">
            {canManage && (
              <label className="form-switch producto-mobile-list-available" htmlFor={`producto-mobile-disponible-${id}`}>
                <span>Disponible</span>
                <input
                  id={`producto-mobile-disponible-${id}`}
                  className="form-check-input producto-mobile-list-switch"
                  type="checkbox"
                  role="switch"
                  checked={estado}
                  onChange={handleDisponibleChange}
                />
              </label>
            )}

            {canManage && (
              <div className="producto-mobile-list-actions">
                <button
                  className="btn-pencil"
                  type="button"
                  aria-label={`Editar ${titulo}`}
                  title="Editar producto"
                  onClick={() => onEdit(id)}
                >
                  <i className="bi bi-pencil-square"></i>
                </button>

                <button
                  className="button-delet"
                  type="button"
                  aria-label={`Eliminar ${titulo}`}
                  title="Eliminar producto"
                  onClick={handleDeleteClick}
                  disabled={deleting}
                >
                  {deleting ? <i className="bi bi-hourglass-split"></i> : <i className="bi bi-trash3"></i>}
                </button>
              </div>
            )}
          </div>
        </article>
      )}

      {isCardsView && (
        <article className="producto-mobile-card">
          <div className="producto-mobile-card-top">
            <div className="producto-mobile-card-image">
              {img ? (
                <img src={img} alt={titulo} />
              ) : (
                <span className="producto-mobile-card-placeholder" aria-hidden="true">
                  <i className="bi bi-image"></i>
                </span>
              )}
            </div>

            <strong className="producto-mobile-card-name">{titulo}</strong>
            <strong className="producto-mobile-card-price">{formatearPrecioClp(price)}</strong>
          </div>

          <div className="producto-mobile-card-bottom">
            {canManage && (
              <label className="form-switch producto-mobile-card-available" htmlFor={`producto-mobile-card-disponible-${id}`}>
                <span>Disponible</span>
                <input
                  id={`producto-mobile-card-disponible-${id}`}
                  className="form-check-input producto-mobile-card-switch"
                  type="checkbox"
                  role="switch"
                  checked={estado}
                  onChange={handleDisponibleChange}
                />
              </label>
            )}

            {canManage && (
              <div className="producto-mobile-card-actions">
                <button
                  className="btn-pencil"
                  type="button"
                  aria-label={`Editar ${titulo}`}
                  title="Editar producto"
                  onClick={() => onEdit(id)}
                >
                  <i className="bi bi-pencil-square"></i>
                </button>

                <button
                  className="button-delet"
                  type="button"
                  aria-label={`Eliminar ${titulo}`}
                  title="Eliminar producto"
                  onClick={handleDeleteClick}
                  disabled={deleting}
                >
                  {deleting ? <i className="bi bi-hourglass-split"></i> : <i className="bi bi-trash3"></i>}
                </button>
              </div>
            )}
          </div>
        </article>
      )}

      <article className="card producto-list-item" id="card-producto">
      <div className="producto-table-cell producto-cell-main">
        <div className="producto-img-wrap">
          {estadoDestacado && <span className="producto-destacado-badge">Destacado</span>}
          {img ? (
            <img src={img} className="card-img-top" alt="" />
          ) : (
            <span className="producto-img-placeholder" aria-hidden="true">
              <i className="bi bi-image"></i>
            </span>
          )}
        </div>

        <div className="producto-main-text">
          <h5 className="titulo-text-card">{titulo}</h5>
          <p className="producto-mobile-meta">
            <span>{categoria || "Sin categoría"}</span>
            <span className="producto-mobile-price-separator" aria-hidden="true">·</span>
            <strong className="producto-mobile-price">{formatearPrecioClp(price)}</strong>
            {variantesCount > 0 && <span>· {variantesCount} {variantesCount === 1 ? "variante" : "variantes"}</span>}
          </p>
          <p className="producto-description-text">{descripcion || categoria || "Sin descripción"}</p>
        </div>
      </div>

      <div className="card-body producto-table-cell producto-cell-category">
        <p className="categoria-text-card">{categoria}</p>
      </div>

      <div className="producto-table-cell producto-cell-price">
        <h4 className="price-text-card">
          {formatearPrecioClp(price)}
        </h4>
      </div>

      {canManage && (
        <>
          <div className="producto-table-cell producto-cell-switch producto-cell-disponible">
            <div className="form-check form-switch producto-switch">
              <label className="form-check-label" htmlFor={`producto-disponible-${id}`}>Disponible</label>

              <input
                id={`producto-disponible-${id}`}
                className="form-check-input"
                type="checkbox"
                checked={estado}
                onChange={handleDisponibleChange}
              />
            </div>
          </div>

          <div className="producto-table-cell producto-cell-switch producto-cell-destacado">
            <div className="form-check form-switch producto-switch">
              <label className="form-check-label" htmlFor={`producto-destacado-${id}`}>Destacado</label>

              <input
                id={`producto-destacado-${id}`}
                className="form-check-input"
                type="checkbox"
                checked={estadoDestacado}
                onChange={handleDestacadoChange}
              />
            </div>
          </div>

          <div className="producto-table-cell div-buttons producto-cell-actions">
            <button className="btn-pencil producto-list-action" type="button" aria-label={`Editar ${titulo}`} title="Editar producto" onClick={() => onEdit(id)}>
              <i className="bi bi-pencil-square"></i>
            </button>

            <button
              type="button"
              className="button-delet producto-list-action"
              aria-label={`Eliminar ${titulo}`}
              title="Eliminar producto"
              onClick={handleDeleteClick}
              disabled={deleting}
            >
              {deleting ? <i className="bi bi-hourglass-split"></i> : <i className="bi bi-trash3"></i>}
            </button>
          </div>
        </>
      )}
      </article>
    </>
  );
}
