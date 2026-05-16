export default function ReservaForm({ onSubmit, enviando, mensaje, error }) {
  return (
    <section className="reserva-section">
      <div className="reserva-card">
        <div className="reserva-header">
          <span>Reserva tu mesa</span>
          <h2>Agenda tu visita</h2>
          <p>
            Completa el formulario y preparate para disfrutar de nuestros mejores platos en un
            ambiente acogedor.
          </p>
        </div>

        <form className="reserva-form" onSubmit={onSubmit}>
          <div className="reserva-row">
            <label>
              <span>Nombre</span>
              <input name="nombre_cliente" autoComplete="name" required />
            </label>
            <label>
              <span>Telefono</span>
              <input name="telefono" type="tel" autoComplete="tel" required />
            </label>
          </div>

          <div className="reserva-row">
            <label>
              <span>Email</span>
              <input name="email" type="email" autoComplete="email" />
            </label>
            <label>
              <span>Fecha</span>
              <input name="fecha" type="date" required />
            </label>
          </div>

          <div className="reserva-row">
            <label>
              <span>Hora</span>
              <input name="hora" type="time" required />
            </label>
            <label>
              <span>Personas</span>
              <input name="cantidad_personas" type="number" min="1" inputMode="numeric" required />
            </label>
          </div>

          <label className="reserva-message-field">
            <span>Mensaje opcional</span>
            <textarea name="mensaje"></textarea>
          </label>

          {mensaje && (
            <div className="alert alert-success" role="status">
              {mensaje}
            </div>
          )}

          {error && (
            <div className="alert alert-danger" role="alert">
              {error}
            </div>
          )}

          <button type="submit" className="button-primary" disabled={enviando}>
            {enviando ? "Enviando reserva..." : "Reservar"}
          </button>
        </form>
      </div>
    </section>
  );
}
