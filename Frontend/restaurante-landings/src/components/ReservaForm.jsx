export default function ReservaForm({ onSubmit }) {
  return (
    <section className="reserva-section">
      <div className="reserva-card">
        <div className="reserva-header">
          <span>Reserva tu mesa</span>
          <h2>Agenda tu visita</h2>
          <p>
            Completa el formulario y prepárate para disfrutar de nuestros mejores platos en un
            ambiente acogedor.
          </p>
        </div>

        <form className="reserva-form" onSubmit={onSubmit}>
          <div className="reserva-row">
            <input name="nombre_cliente" placeholder="Nombre" required />
            <input name="telefono" placeholder="Teléfono" required />
          </div>

          <div className="reserva-row">
            <input name="email" type="email" placeholder="Email" />
            <input name="fecha" type="date" required />
          </div>

          <div className="reserva-row">
            <input name="hora" type="time" required />
            <input name="cantidad_personas" type="number" min="1" placeholder="Personas" required />
          </div>

          <textarea name="mensaje" placeholder="Mensaje opcional"></textarea>

          <button type="submit" className="button-primary">
            Reservar ahora
          </button>
        </form>
      </div>
    </section>
  );
}
