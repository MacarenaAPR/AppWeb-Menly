import { useState } from "react";
import { loginRequest } from "../api/auth";
import "../styles/login.css";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: "",
    password: "",
  });
  const [error, setError] = useState("");

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    try {
      const data = await loginRequest(form.username, form.password);

      if (!data.restaurante?.slug) {
        setError("Este usuario no tiene un restaurante asignado");
        return;
      }

      localStorage.setItem("access", data.access);
      localStorage.setItem("refresh", data.refresh);
      localStorage.setItem("user", JSON.stringify(data.user));
      localStorage.setItem("restaurante", JSON.stringify(data.restaurante));

      navigate(`/dashboard/${data.restaurante.slug}`);
    } catch {
      setError("Usuario o contraseña incorrectos");
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
            <label htmlFor="username">Usuario</label>
            <input
              placeholder="usuario"
              id="username"
              type="text"
              name="username"
              value={form.username}
              onChange={handleChange}
              required
            />

            <label htmlFor="password">Contraseña</label>
            <input
              placeholder="*******"
              id="password"
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              required
            />

            <div className="div-btn">
              <button type="submit">Ingresar</button>
            </div>
          </form>

          {error && <p className="error">{error}</p>}

          <a href="/">¿Has olvidado la contraseña?</a>
        </div>
      </div>
    </div>
  );
}
