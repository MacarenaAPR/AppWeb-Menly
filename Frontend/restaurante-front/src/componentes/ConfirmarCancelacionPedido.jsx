import "../styles/ConfirmarCancelacionPedido.css";

export default function ConfirmarCancelacionPedido({
  abierto,
  cargando = false,
  error = "",
  onVolver,
  onConfirmar,
}) {
  if (!abierto) return null;

  const cerrarDesdeFondo = (event) => {
    if (event.target === event.currentTarget && !cargando) onVolver();
  };

  return (
    <div
      className="confirmar-cancelacion-bg"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirmar-cancelacion-title"
      onMouseDown={cerrarDesdeFondo}
    >
      <section className="confirmar-cancelacion-modal">
        <button
          className="confirmar-cancelacion-close"
          type="button"
          aria-label="Cerrar confirmación"
          onClick={onVolver}
          disabled={cargando}
        >
          <i className="bi bi-x-lg"></i>
        </button>

        <div className="confirmar-cancelacion-icon" aria-hidden="true">
          <i className="bi bi-exclamation-triangle"></i>
        </div>
        <h2 id="confirmar-cancelacion-title">Cancelar pedido</h2>
        <p>¿Estás seguro de cancelar este pedido?</p>
        <small>Esta acción no se puede deshacer y el pedido no podrá volver a un estado anterior.</small>

        {error && <p className="confirmar-cancelacion-error" role="alert">{error}</p>}

        <div className="confirmar-cancelacion-actions">
          <button type="button" onClick={onVolver} disabled={cargando}>Volver</button>
          <button type="button" onClick={onConfirmar} disabled={cargando}>
            {cargando ? "Cancelando..." : "Sí, cancelar pedido"}
          </button>
        </div>
      </section>
    </div>
  );
}
