import "../styles/style-componentes.css";
import { cerrarSesionAdmin } from "../api";

export default function ButtonLogout({ icon, name }) {
  const handleLogout = async () => {
    await cerrarSesionAdmin({ motivo: "manual" });
  };

  return (
    <button className="btn-cerrar-sesion" onClick={handleLogout} type="button">
      <i>{icon}</i>
      <p>{name}</p>
    </button>
  );
}
