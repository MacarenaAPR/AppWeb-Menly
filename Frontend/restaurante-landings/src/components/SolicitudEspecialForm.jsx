export default function SolicitudEspecialForm({
  restauranteId,
  onSubmit,
  enviando,
  mensaje,
  error,
}) {
  return (
    <section className="reserva-section">
      <div className="reserva-card">
        <div className="reserva-header">
          <span>Pedidos especiales</span>
          <h2>Cuéntanos qué necesitas</h2>
          <p>
            Completa la solicitud y el restaurante se pondrá en contacto contigo para revisar
            los detalles.
          </p>
        </div>

        <form className="reserva-form" onSubmit={onSubmit}>
          <input type="hidden" name="restaurante_id" value={restauranteId || ""} />

          <div className="reserva-row">
            <label>
              <span>Nombre</span>
              <input type="text" name="nombre" required />
            </label>
            <label>
              <span>Apellido</span>
              <input type="text" name="apellido" required />
            </label>
          </div>

          <div className="reserva-row">
            <label>
              <span>Fecha del evento</span>
              <input type="date" name="fecha_evento" required />
            </label>
            <label>
              <span>Teléfono de contacto</span>
              <input type="tel" name="telefono_contacto" required />
            </label>
          </div>

          <label>
            <span>Email de contacto</span>
            <input type="email" name="email_contacto" required />
          </label>

          <label className="reserva-message-field">
            <span>Descripción de la solicitud</span>
            <textarea name="descripcion_solicitud" rows="4" required></textarea>
          </label>

          {mensaje && <p className="form-success">{mensaje}</p>}
          {error && <p className="form-error">{error}</p>}

          <button className="button-primary" type="submit" disabled={enviando}>
            {enviando ? "Enviando..." : "Enviar"}
          </button>
        </form>
      </div>
    </section>
  );
}
