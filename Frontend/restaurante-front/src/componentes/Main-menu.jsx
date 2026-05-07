import logo from "../assets/logoMenly.png";
import ButtonMain from "./link-menu";
import ButtonLogout from "./btn-cerrar-sesion";
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { authFetch, buildMenuUrl } from "../api";
import { permisosPorRol } from "../utils/permisos";

export default function MainMenu(){
    const [data, setData] = useState(null);
    const { slug } = useParams();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const navigate = useNavigate();
 useEffect(() => {
    const fetchRestaurante = async () => {
      try {
        const token = localStorage.getItem("access");

        if (!token) {
          navigate("/");
          return;
        }

        const response = await authFetch("/mi-restaurante/", {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error("Error al cargar datos");
        }

        const result = await response.json();

        if (slug && slug !== result.restaurante.slug) {
          navigate(`/dashboard/${result.restaurante.slug}`, { replace: true });
          return;
        }

        setData(result);
      } catch {
        setError("No se pudieron cargar los datos");
      } finally {
        setLoading(false);
      }
    };

    fetchRestaurante();
  }, [slug, navigate]);

  if (loading) {
    return <p>Cargando dashboard...</p>;
  }

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  if (!data) {
    return <p>No hay datos disponibles</p>;
  }

  const { restaurante, usuario } = data;
  const permisos = permisosPorRol(usuario?.rol || restaurante?.rol);
  const paginaWeb = restaurante?.sitio_web?.trim();
  const paginaWebUrl = paginaWeb
    ? paginaWeb.match(/^https?:\/\//i)
      ? paginaWeb
      : `http://${paginaWeb}`
    : buildMenuUrl(restaurante.slug);

    return(
        <section className="menu-main">
            <div className="div-logo">
                <img src={logo} alt="Logo-menu" />
            </div>
            <ul className="nav flex-column">
                <li className="nav-item">
                    <ButtonMain
                        icon={<i className="bi bi-columns-gap"></i>}
                        name="Inicio"
                        onClick={() => navigate(`/dashboard/${restaurante.slug}`)}>
                    </ButtonMain>
                </li>
                <li className="nav-item">
                    <ButtonMain
                        icon ={<i className="bi bi-book-half"></i>}
                        name="Carta/Productos"
                        onClick={() => navigate(`/carta-productos/${restaurante.slug}`)}>
                    </ButtonMain>
                </li>
                {permisos.canViewBitacora && (
                <li className="nav-item">
                  <ButtonMain
                    icon={<i className="bi bi-clock-history"></i>}
                    name="Bitácora"
                    onClick={() => navigate(`/historial`)}
                  />
                </li>
                )}
                <li className="nav-item">
                    <ButtonMain
                        icon ={<i className="bi bi-calendar3"></i>}
                        name="Reservas"
                        onClick={() => navigate(`/dashboard/${restaurante.slug}/reservas`)}>
                    </ButtonMain>
                </li>
                {/*<li class="nav-item">
                    <ButtonMain
                        icon ={<i class="bi bi-graph-up"></i>}
                        name="Reportes">
                    </ButtonMain>
                </li>*/}
                <li className="nav-item">
                    <ButtonMain
                        icon={<i className="bi bi-globe"></i>}
                        name="Mi página web"
                        onClick={() => window.open(paginaWebUrl, "_blank")}>
                    </ButtonMain>
                </li>
                {permisos.canAccessConfiguracion && (
                <li className="nav-item">
                    <ButtonMain
                        icon={<i className="bi bi-gear"></i>}
                        name="Configuraciones"
                        onClick={() => navigate(`/dashboard/${restaurante.slug}/configuracion`)}>
                    </ButtonMain>
                </li>
                )}
            </ul>
            <div className="div-cerrar-sesion">
                <ButtonLogout
                    icon={<i className="bi bi-box-arrow-right"></i>}
                    name="Cerrar sesión">
                </ButtonLogout>         
            </div>
        </section>
    );
}
