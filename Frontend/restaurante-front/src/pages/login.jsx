import { useState } from "react";
import { loginRequest, passwordResetRequest } from "../api/auth";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/login.css";
import { useNavigate } from "react-router-dom";

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
      <div className="overlay">
        <div className="login-card">
          <h1>Iniciar sesión</h1>
          <h2><span>M</span>enly</h2>
          <p>Gestiona tu restaurante sin caos</p>

          <form onSubmit={handleSubmit}>
            <label htmlFor="email">Correo electrónico</label>
            <input
              placeholder="correo@ejemplo.com"
              id="email"
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              autoComplete="email"
              required
            />

            <label htmlFor="password">Contraseña</label>
            <div className="password-field">
              <input
                placeholder="*******"
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

            <div className="div-btn">
              <button type="submit">Ingresar</button>
            </div>
          </form>

          {error && <p className="error">{error}</p>}

          <button
            type="button"
            className="forgot-password-link"
            onClick={() => {
              setResetOpen((open) => !open);
              setResetEmail(form.email);
              setResetMessage("");
              setResetError("");
            }}
          >
            ¿Has olvidado la contraseña?
          </button>

          {resetOpen && (
            <form className="password-reset-form" onSubmit={handleResetSubmit}>
              <label htmlFor="reset-email">Correo electrónico</label>
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

              <button type="submit" disabled={resetLoading}>
                {resetLoading ? "Enviando..." : "Enviar solicitud"}
              </button>

              {resetMessage && <p className="success">{resetMessage}</p>}
              {resetError && <p className="error">{resetError}</p>}
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
