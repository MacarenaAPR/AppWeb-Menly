import "../styles/style-componentes.css";
import { useNavigate } from "react-router-dom";
import { authFetch } from "../api";

export default function ButtonLogout({ icon, name }) {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      const refresh = localStorage.getItem("refresh");

      if (refresh) {
        await authFetch("/logout/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ refresh }),
        });
      }
    } catch {
      // El cierre local se ejecuta igual aunque falle el endpoint.
    } finally {
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      localStorage.removeItem("user");
      localStorage.removeItem("restaurante");

      navigate("/", { replace: true });
    }
  };

  return (
    <button className="btn-cerrar-sesion" onClick={handleLogout} type="button">
      <i>{icon}</i>
      <p>{name}</p>
    </button>
  );
}
