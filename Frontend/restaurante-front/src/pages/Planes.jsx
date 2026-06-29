import { Fragment, useState } from "react";
import "bootstrap-icons/font/bootstrap-icons.css";
import PublicNavbar from "../componentes/public/PublicNavbar";
import { buildApiUrl } from "../api";
import "../styles/SaberMas.css";
import "../styles/Planes.css";

const MENSAJE_EXITO = "Consulta enviada correctamente. Te contactaremos pronto.";

const planCards = [
  {
    nombre: "Plan Básico",
    precio: "$24.990",
    descripcion: "Ideal para comenzar tu presencia digital.",
  },
  {
    nombre: "Plan Pro",
    precio: "$39.990",
    etiqueta: "Más popular",
    descripcion: "Para restaurantes que quieren vender, organizar y medir mejor.",
  },
];

const categorias = [
  {
    nombre: "Presencia Digital",
    icono: "bi-globe2",
    items: [
      ["Landing web básica", true, true],
      ["Menú Digital QR", true, true],
      ["Responsive", true, true],
      ["SEO básico", true, true],
      ["SEO avanzado", false, true],
      ["Dominio propio opcional", false, true],
      ["Branding parcial", false, true],
      ["Galería de imágenes", true, true],
      ["Redes sociales", true, true],
    ],
  },
  {
    nombre: "Gestión del Restaurante",
    icono: "bi-shop-window",
    items: [
      ["Gestión de productos", true, true],
      ["Gestión de categorías", true, true],
      ["Productos destacados", true, true],
      ["Disponibilidad", true, true],
      ["Horarios", true, true],
      ["Configuración restaurante", true, true],
      ["Dashboard básico", true, true],
      ["Dashboard completo", false, true],
    ],
  },
  {
    nombre: "Pedidos",
    icono: "bi-bag-check",
    items: [
      ["Carrito de pedidos por WhatsApp", true, true],
      ["Historial de pedidos", true, true],
      ["Delivery / Retiro", true, true],
      ["Seguimiento del pedido", false, true],
      ["Estados del pedido", false, true],
      ["Tracking público", false, true],
    ],
  },
  {
    nombre: "Reservas",
    icono: "bi-calendar-check",
    items: [
      ["Reservas online", true, true],
      ["Calendario", true, true],
      ["Confirmaciones", true, true],
      ["Historial de reservas", true, true],
    ],
  },
  {
    nombre: "Solicitudes",
    icono: "bi-chat-square-heart",
    items: [
      ["Solicitudes especiales", true, true],
      ["Conversión de solicitudes a pedido", false, true],
    ],
  },
  {
    nombre: "Estadísticas",
    icono: "bi-graph-up-arrow",
    items: [
      ["Visitas", true, true],
      ["Productos más vistos", true, true],
      ["Productos más vendidos", false, true],
      ["Ventas mensuales", false, true],
      ["Ventas anuales", false, true],
      ["Reportes PDF", false, true],
      ["Reportes Excel", false, true],
    ],
  },
  {
    nombre: "Soporte",
    icono: "bi-headset",
    items: [
      ["Actualizaciones", true, true],
      ["Soporte estándar", true, true],
      ["Soporte prioritario", false, true],
      ["Capacitación inicial", true, true],
      ["Capacitación completa", false, true],
    ],
  },
];

const formInicial = {
  nombre: "",
  restaurante: "",
  correo: "",
  telefono: "",
  ciudad: "",
  plan: "No estoy seguro",
  mensaje: "",
};

function EstadoPlan({ incluido }) {
  return incluido ? (
    <span className="planes-check" aria-label="Incluido">
      <i className="bi bi-check-circle-fill" aria-hidden="true"></i>
    </span>
  ) : (
    <span className="planes-dash" aria-label="No incluido">
      <i className="bi bi-x-lg" aria-hidden="true"></i>
    </span>
  );
}

export default function Planes() {
  const [openCategory, setOpenCategory] = useState(0);
  const [formData, setFormData] = useState(formInicial);
  const [errors, setErrors] = useState({});
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined, general: undefined }));
    setSuccess("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setErrors({});
    setSuccess("");

    try {
      const response = await fetch(buildApiUrl("/contacto/planes/"), {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });
      const data = await response.json().catch(() => null);

      if (!response.ok) {
        if (data && typeof data === "object" && !data.error) {
          setErrors(data);
        } else {
          setErrors({
            general: data?.error || "No pudimos enviar tu consulta. Intenta nuevamente.",
          });
        }
        return;
      }

      setSuccess(data?.message || MENSAJE_EXITO);
      setFormData(formInicial);
    } catch (error) {
      setErrors({ general: "No pudimos enviar tu consulta. Intenta nuevamente." });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="planes-page">
      <PublicNavbar />

      <section className="planes-hero">
        <div className="planes-hero__copy">
          <span className="planes-kicker">Planes Menly</span>
          <h1>Compara los planes de Menly</h1>
          <p>
            Elige el plan que mejor se adapta a tu restaurante. Comienza simple y
            crece cuando necesites más control.
          </p>
        </div>

        <div className="planes-summary-grid" aria-label="Resumen de planes">
          {planCards.map((plan) => (
            <article
              className={`planes-summary-card ${plan.etiqueta ? "is-featured" : ""}`}
              key={plan.nombre}
            >
              {plan.etiqueta && <span>{plan.etiqueta}</span>}
              <h2>{plan.nombre}</h2>
              <div className="planes-summary-price">
                <strong>{plan.precio}</strong>
                <small>/mes</small>
              </div>
              <p>{plan.descripcion}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="planes-section" aria-labelledby="comparativa-title">
        <div className="planes-section__heading">
          <span className="planes-kicker">Comparativa</span>
          <h2 id="comparativa-title">Funcionalidades por plan</h2>
          <p>Compara lo incluido en cada plan sin ruido ni extras innecesarios.</p>
        </div>

        <div className="planes-accordion-list">
          {categorias.map((categoria, index) => {
            const isOpen = openCategory === index;
            const panelId = `planes-category-${index}`;

            return (
              <article className={`planes-accordion ${isOpen ? "is-open" : ""}`} key={categoria.nombre}>
                <button
                  type="button"
                  className="planes-accordion__trigger"
                  aria-expanded={isOpen}
                  aria-controls={panelId}
                  onClick={() => setOpenCategory(isOpen ? null : index)}
                >
                  <span>
                    <i className={`bi ${categoria.icono}`} aria-hidden="true"></i>
                    {categoria.nombre}
                  </span>
                  <i className="bi bi-chevron-down" aria-hidden="true"></i>
                </button>

                <div className="planes-accordion__panel" id={panelId}>
                  <div className="planes-table-shell">
                    <table className="planes-table">
                      <thead>
                        <tr>
                          <th>Funcionalidad</th>
                          <th>Básico</th>
                          <th className="is-pro">Pro</th>
                        </tr>
                      </thead>
                      <tbody>
                        {categoria.items.map(([nombre, basico, pro]) => (
                          <tr key={`${categoria.nombre}-${nombre}`}>
                            <td>{nombre}</td>
                            <td>
                              <EstadoPlan incluido={basico} />
                            </td>
                            <td>
                              <EstadoPlan incluido={pro} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </article>
            );
          })}
        </div>

        <div className="planes-table-shell planes-table-shell--legacy" aria-hidden="true">
          <table className="planes-table">
            <thead>
              <tr>
                <th>Funcionalidad</th>
                <th>Básico</th>
                <th className="is-pro">Pro</th>
              </tr>
            </thead>
            <tbody>
              {categorias.map((categoria) => (
                <Fragment key={categoria.nombre}>
                  <tr className="planes-category-row">
                    <td colSpan="3">
                      <i className={`bi ${categoria.icono}`} aria-hidden="true"></i>
                      {categoria.nombre}
                    </td>
                  </tr>
                  {categoria.items.map(([nombre, basico, pro]) => (
                    <tr key={`${categoria.nombre}-${nombre}`}>
                      <td>{nombre}</td>
                      <td>
                        <EstadoPlan incluido={basico} />
                      </td>
                      <td>
                        <EstadoPlan incluido={pro} />
                      </td>
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="planes-contact" id="contacto-planes">
        <div className="planes-contact__copy">
          <span className="planes-kicker">Contacto</span>
          <h2>¿Quieres saber qué plan te conviene?</h2>
          <p>
            Cuéntanos sobre tu restaurante y te ayudamos a elegir entre Básico o Pro.
          </p>
        </div>

        <form className="planes-form" onSubmit={handleSubmit} noValidate>
          {errors.general && <p className="planes-form-alert is-error">{errors.general}</p>}
          {success && <p className="planes-form-alert is-success">{success}</p>}

          <label>
            Nombre
            <input name="nombre" value={formData.nombre} onChange={handleChange} required />
            {errors.nombre && <span>{errors.nombre}</span>}
          </label>

          <label>
            Nombre del restaurante
            <input name="restaurante" value={formData.restaurante} onChange={handleChange} required />
            {errors.restaurante && <span>{errors.restaurante}</span>}
          </label>

          <label>
            Correo
            <input name="correo" type="email" value={formData.correo} onChange={handleChange} required />
            {errors.correo && <span>{errors.correo}</span>}
          </label>

          <label>
            Teléfono
            <input name="telefono" value={formData.telefono} onChange={handleChange} required />
            {errors.telefono && <span>{errors.telefono}</span>}
          </label>

          <label>
            Ciudad
            <input name="ciudad" value={formData.ciudad} onChange={handleChange} required />
            {errors.ciudad && <span>{errors.ciudad}</span>}
          </label>

          <label>
            Plan de interés
            <select name="plan" value={formData.plan} onChange={handleChange} required>
              <option value="Básico">Básico</option>
              <option value="Pro">Pro</option>
              <option value="No estoy seguro">No estoy seguro</option>
            </select>
            {errors.plan && <span>{errors.plan}</span>}
          </label>

          <label className="planes-form__message">
            Mensaje
            <textarea name="mensaje" value={formData.mensaje} onChange={handleChange} rows="5" required />
            {errors.mensaje && <span>{errors.mensaje}</span>}
          </label>

          <button className="planes-submit" type="submit" disabled={submitting}>
            {submitting ? "Enviando..." : "Enviar consulta"}
          </button>
        </form>
      </section>
    </main>
  );
}
