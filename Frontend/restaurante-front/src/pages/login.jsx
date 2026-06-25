import { useState } from "react";
import { loginRequest, passwordResetRequest } from "../api/auth";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/login.css";
import { useNavigate } from "react-router-dom";
import logoMenly from "../assets/logoMenly2.png";
import recursoLogin1 from "../assets/recursologin1.png";
import recursoLogin2 from "../assets/recursologin2.png";
import recursoLogin3 from "../assets/recursologin3.png";

const MENLY_WHATSAPP_URL =
  "https://wa.me/56988424939?text=Hola%2C%20quiero%20saber%20m%C3%A1s%20sobre%20Menly";

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetMessage, setResetMessage] = useState("");
  const [resetError, setResetError] = useState("");
  const [resetLoading, setResetLoading] = useState(false);

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
      const data = await loginRequest(email, form.password);

      if (!data.restaurante?.slug) {
        setError("Este usuario no tiene un restaurante asignado");
        return;
      }

      localStorage.setItem("access", data.access);
      localStorage.setItem("refresh", data.refresh);
      localStorage.setItem("user", JSON.stringify(data.user));
      localStorage.setItem("restaurante", JSON.stringify(data.restaurante));

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
        <section className="login-showcase" aria-label="Beneficios de Menly">
          <div className="login-phones" aria-label="Aplicaciones de Menly">
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

        <section className="login-panel">
          <div className="login-card">
            <h1 className="login-title">
              <span>I</span>nicia <span>S</span>esion
            </h1>

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

            <button type="button" className="login-contact-link">
              ¿ No tienes cuenta ? contáctanos
            </button>
          </div>
        </section>
      </main>

      <footer className="login-footer">
        @ Menly.cl desarrollado por MPR.ING
      </footer>
    </div>
  );
}
