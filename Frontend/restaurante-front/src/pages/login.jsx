import { useEffect, useState } from "react";
import { loginRequest, passwordResetRequest } from "../api/auth";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/login.css";
import { useNavigate } from "react-router-dom";
import logoMenly from "../assets/logoMenly2.png";
import recursoLogin1 from "../assets/recursologin1.png";
import recursoLogin2 from "../assets/recursologin2.png";
import recursoLogin3 from "../assets/recursologin3.png";
import {
  consumirMensajeCierreAdmin,
  iniciarSesionAdmin,
  obtenerEmailRecordado,
  tieneSesionAdmin,
} from "../session/adminSession";
import { restaurarSesionAdmin } from "../api";

const MENLY_WHATSAPP_URL =
  "https://wa.me/56988424939?text=Hola%2C%20quiero%20saber%20m%C3%A1s%20sobre%20Menly";
const MENLY_CONTACT_EMAIL = "menly.contacto@gmail.com";
const MENLY_CONTACT_MAILTO = `mailto:${MENLY_CONTACT_EMAIL}?subject=${encodeURIComponent(
  "Solicitud de información - Menly"
)}&body=${encodeURIComponent(
  `Hola equipo de Menly,

Me gustaría obtener información sobre la plataforma para mi restaurante.

Nombre:
Restaurante:
Ciudad:
Teléfono:

Quedo atento(a).`
)}`;

const SEO_TITLE =
  "Menly | Páginas web para restaurantes con menú digital, reservas y pedidos por WhatsApp";
const SEO_DESCRIPTION =
  "Menly ayuda a restaurantes, cafeterías y negocios gastronómicos a tener una página web profesional con menú digital, reservas online, pedidos por WhatsApp y panel de administración.";
const SEO_CANONICAL = "https://menly.cl/";
const MENLY_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Menly",
  url: SEO_CANONICAL,
  description:
    "Plataforma para crear páginas web de restaurantes con menú digital, reservas y pedidos por WhatsApp.",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
};

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState(() => ({
    email: obtenerEmailRecordado(),
    password: "",
  }));
  const [recordarme, setRecordarme] = useState(false);
  const [error, setError] = useState("");
  const [sessionMessage] = useState(() => consumirMensajeCierreAdmin());
  const [showPassword, setShowPassword] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetMessage, setResetMessage] = useState("");
  const [resetError, setResetError] = useState("");
  const [resetLoading, setResetLoading] = useState(false);

  useEffect(() => {
    if (!tieneSesionAdmin()) return undefined;
    let active = true;
    restaurarSesionAdmin().then((restored) => {
      if (!active || !restored) return;
      try {
        const restaurante = JSON.parse(localStorage.getItem("restaurante") || "null");
        if (restaurante?.slug) navigate(`/dashboard/${restaurante.slug}`, { replace: true });
      } catch {
        // El formulario queda disponible si faltan datos locales de la sesión.
      }
    });
    return () => {
      active = false;
    };
  }, [navigate]);

  useEffect(() => {
    document.title = SEO_TITLE;

    const setMeta = (selector, attributes) => {
      let element = document.head.querySelector(selector);
      if (!element) {
        element = document.createElement("meta");
        document.head.appendChild(element);
      }

      Object.entries(attributes).forEach(([name, value]) => {
        element.setAttribute(name, value);
      });
    };

    setMeta('meta[name="description"]', {
      name: "description",
      content: SEO_DESCRIPTION,
    });
    setMeta('meta[name="robots"]', {
      name: "robots",
      content: "index, follow",
    });

    let canonical = document.head.querySelector('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.setAttribute("rel", "canonical");
      document.head.appendChild(canonical);
    }
    canonical.setAttribute("href", SEO_CANONICAL);

    let jsonLd = document.getElementById("menly-software-application-jsonld");
    if (!jsonLd) {
      jsonLd = document.createElement("script");
      jsonLd.id = "menly-software-application-jsonld";
      jsonLd.type = "application/ld+json";
      document.head.appendChild(jsonLd);
    }
    jsonLd.textContent = JSON.stringify(MENLY_JSON_LD);
  }, []);

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

  const handleResetSubmit = async (e) => {
    e.preventDefault();
    setResetMessage("");
    setResetError("");

    const email = resetEmail.trim().toLowerCase();

    if (!email) {
      setResetError("Ingresa tu correo electrónico");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setResetError("Ingresa un correo electrónico válido");
      return;
    }

    try {
      setResetLoading(true);
      const data = await passwordResetRequest(email);
      setResetMessage(
        data.message ||
        "Si el correo está registrado, el administrador será notificado."
      );
    } catch (error) {
      setResetError(
        error.response?.data?.email ||
        "No se pudo enviar la solicitud. Intenta nuevamente."
      );
    } finally {
      setResetLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const email = form.email.trim().toLowerCase();

    if (!email) {
      setError("Ingresa tu correo electrónico");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Ingresa un correo electrónico válido");
      return;
    }

    if (!form.password) {
      setError("Ingresa tu contraseña");
      return;
    }

    try {
      const data = await loginRequest(email, form.password, recordarme);

      if (!data.restaurante?.slug) {
        setError("Este usuario no tiene un restaurante asignado");
        return;
      }

      iniciarSesionAdmin(data, { recordarme, email });

      navigate(`/dashboard/${data.restaurante.slug}`);
    } catch (error) {
      setError(
        error.response?.data?.detail ||
        "Correo o contraseña incorrectos"
      );
    }
  };

  return (
    <div className="login-page">
      <header className="login-header">
        <div className="login-brand">
          <img src={logoMenly} alt="Menly" />
        </div>

        <div className="login-actions">
          <button
            type="button"
            className="login-action login-action-primary"
            onClick={() => window.open(MENLY_WHATSAPP_URL, "_blank", "noopener,noreferrer")}
          >
            Contáctanos
          </button>
          <button
            type="button"
            className="login-action login-action-outline"
            onClick={() => navigate("/saber-mas")}
          >
            Saber mas
          </button>
        </div>
      </header>

      <main className="login-content">
        <section className="login-left" aria-label="Menly para restaurantes">
          <section className="login-seo-content" aria-labelledby="menly-public-title">
            <p className="login-seo-kicker">Plataforma web para gastronomía</p>
            <h1 id="menly-public-title">
              Menly: páginas web para restaurantes con menú digital, reservas y pedidos por WhatsApp
            </h1>
            <p>
              Menly ayuda a restaurantes, cafeterías y negocios gastronómicos a tener una página web profesional con menú digital, reservas online, pedidos por WhatsApp y panel de administración.
            </p>

            <div className="login-seo-features" aria-label="Funciones principales de Menly">
              <article>
                <h2>Menú digital para restaurantes</h2>
                <p>Publica productos, categorías y precios en una carta online clara para tus clientes.</p>
              </article>
              <article>
                <h2>Reservas online</h2>
                <p>Recibe solicitudes de reserva desde la página web de tu restaurante.</p>
              </article>
              <article>
                <h2>Pedidos por WhatsApp</h2>
                <p>Conecta la intención de compra de tus clientes con una conversación directa por WhatsApp.</p>
              </article>
              <article>
                <h2>Panel de administración</h2>
                <p>Gestiona menú, reservas, pedidos y configuración del negocio desde un solo lugar.</p>
              </article>
              <article>
                <h2>Métricas para el negocio</h2>
                <p>Revisa información útil para entender el rendimiento digital de tu restaurante.</p>
              </article>
            </div>
          </section>

          <div className="login-carousel" aria-label="Aplicaciones de Menly">
            <div className="login-phones">
            <div className="login-phone login-phone-left">
              <img
                src={recursoLogin1}
                alt="Panel de gestión Menly en un celular"
              />
            </div>
            <div className="login-phone login-phone-center">
              <img
                src={recursoLogin3}
                alt="Carta y productos Menly en un celular"
              />
            </div>
            <div className="login-phone login-phone-right">
              <img
                src={recursoLogin2}
                alt="Página web de restaurante creada con Menly"
              />
            </div>
            </div>
          </div>

          <div className="login-benefits">
            <article className="login-benefit">
              <h2>
                <i className="bi bi-globe2" aria-hidden="true"></i>
                Tu propia página web
              </h2>
              <p>Sitio web para tu negocio con tu marca y menú digital.</p>
            </article>

            <article className="login-benefit">
              <h2>
                <i className="bi bi-shop" aria-hidden="true"></i>
                Gestiona tu negocio
              </h2>
              <p>
                Administra productos, reservas, pedidos y solicitudes especiales.
              </p>
            </article>

            <article className="login-benefit">
              <h2>
                <i className="bi bi-bar-chart-fill" aria-hidden="true"></i>
                Analítica del negocio
              </h2>
              <p>
                Analiza el rendimiento de tu negocio y toma mejores decisiones.
              </p>
            </article>
          </div>
        </section>

        <section className="login-card-wrapper">
          <div className="login-card">
            <h2 className="login-title">
              <span>I</span>nicia <span>S</span>esion
            </h2>

            <form className="login-form" onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor="email">Correo</label>
                <input
                  id="email"
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  autoComplete="email"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="password">Contraseña</label>
                <div className="password-field">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={form.password}
                    onChange={handleChange}
                    autoComplete="current-password"
                    required
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                    onClick={() => setShowPassword((visible) => !visible)}
                  >
                    <i
                      className={`bi ${showPassword ? "bi-eye-slash" : "bi-eye"}`}
                      aria-hidden="true"
                    ></i>
                  </button>
                </div>
              </div>

              <label className="login-remember">
                <input
                  type="checkbox"
                  checked={recordarme}
                  onChange={(event) => setRecordarme(event.target.checked)}
                />
                <span>Recuérdame</span>
              </label>

              {sessionMessage && <p className="form-message success">{sessionMessage}</p>}
              {error && <p className="form-message error">{error}</p>}

              <button className="login-submit" type="submit">
                Iniciar Sesion
              </button>
            </form>

            <button
              type="button"
              className="forgot-password-link"
              aria-expanded={resetOpen}
              onClick={() => {
                setResetOpen((open) => !open);
                setResetEmail(form.email);
                setResetMessage("");
                setResetError("");
              }}
            >
              ¿ haz olvidado la contraseña ?
            </button>

            {resetOpen && (
              <form className="password-reset-form" onSubmit={handleResetSubmit}>
                <div className="form-group">
                  <label htmlFor="reset-email">Correo</label>
                  <input
                    id="reset-email"
                    type="email"
                    name="reset-email"
                    placeholder="correo@ejemplo.com"
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                    autoComplete="email"
                    required
                  />
                </div>

                <button className="reset-submit" type="submit" disabled={resetLoading}>
                  {resetLoading ? "Enviando..." : "Enviar solicitud"}
                </button>

                {resetMessage && <p className="form-message success">{resetMessage}</p>}
                {resetError && <p className="form-message error">{resetError}</p>}
              </form>
            )}

            <a className="login-contact-link" href={MENLY_CONTACT_MAILTO}>
              ¿ No tienes cuenta ? contáctanos
            </a>
          </div>
        </section>
      </main>

      <footer className="login-footer">
        @ Menly.cl desarrollado por MPR.ING
      </footer>
    </div>
  );
}
