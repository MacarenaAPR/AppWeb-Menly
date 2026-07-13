import logo from "../assets/logoMenly.png";
import logoMobile from "../assets/logoMenly2.png";
import ButtonMain from "./link-menu";
import ButtonLogout from "./btn-cerrar-sesion";
import { useEffect, useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { authFetch } from "../api";
import { permisosPorRol } from "../utils/permisos";
import { LuShoppingCart } from "react-icons/lu";
import { TbMessage2Star } from "react-icons/tb";
import { tieneSesionAdmin } from "../session/adminSession";

export default function MainMenu({
    mobileMenuOpen: controlledMobileMenuOpen,
    onMobileMenuOpenChange,
} = {}){
    const [data, setData] = useState(null);
    const [internalMobileMenuOpen, setInternalMobileMenuOpen] = useState(false);
    const { slug } = useParams();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const navigate = useNavigate();
    const location = useLocation();
 useEffect(() => {
    const fetchRestaurante = async () => {
      try {
        if (!tieneSesionAdmin()) {
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
  const restauranteSlug = restaurante?.slug;
  const paginaWebUrl = restauranteSlug ? `https://${restauranteSlug}.menly.cl` : "";
  const mobileMenuOpen = controlledMobileMenuOpen ?? internalMobileMenuOpen;
  const setMobileMenuOpen = (isOpen) => {
    if (controlledMobileMenuOpen === undefined) {
      setInternalMobileMenuOpen(isOpen);
    }
    onMobileMenuOpenChange?.(isOpen);
  };

  const closeMobileMenu = () => setMobileMenuOpen(false);
  const navigateAndClose = (path) => {
    navigate(path);
    closeMobileMenu();
  };
  const openPageAndClose = () => {
    if (!paginaWebUrl) return;

    window.open(paginaWebUrl, "_blank", "noopener,noreferrer");
    closeMobileMenu();
  };

  const menuItems = [
    {
      key: "inicio",
      icon: <i className="bi bi-columns-gap"></i>,
      name: "Inicio",
      isActive: location.pathname === `/dashboard/${restaurante.slug}`,
      onClick: () => navigateAndClose(`/dashboard/${restaurante.slug}`),
    },
    (restaurante.pedidos_pos === true || restaurante.carrito_whatsapp_activo === true || restaurante.solicitudes_especiales_activas === true) && permisos.canManageReservas && {
      key: "pedidos",
      icon: <LuShoppingCart />,
      name: "Pedidos",
      isActive: location.pathname === `/dashboard/${restaurante.slug}/pedidos`,
      onClick: () => navigateAndClose(`/dashboard/${restaurante.slug}/pedidos`),
    },
    {
      key: "productos",
      icon: <i className="bi bi-book-half"></i>,
      name: "Carta/Productos",
      isActive:
        location.pathname.startsWith(`/carta-productos/${restaurante.slug}`) ||
        location.pathname === `/carta-add/${restaurante.slug}`,
      onClick: () => navigateAndClose(`/carta-productos/${restaurante.slug}`),
    },
    restaurante.solicitudes_especiales_activas === true && permisos.canManageSolicitudesEspeciales && {
      key: "solicitudes-especiales",
      icon: <TbMessage2Star />,
      name: "Solicitudes especiales",
      isActive: location.pathname === `/dashboard/${restaurante.slug}/solicitudes-especiales`,
      onClick: () => navigateAndClose(`/dashboard/${restaurante.slug}/solicitudes-especiales`),
    },
    restaurante.reservas_activas === true && {
      key: "reservas",
      icon: <i className="bi bi-calendar3"></i>,
      name: "Reservas",
      isActive: location.pathname === `/dashboard/${restaurante.slug}/reservas`,
      onClick: () => navigateAndClose(`/dashboard/${restaurante.slug}/reservas`),
    },
    
    restaurante.metricas_activas === true && permisos.canViewMetricas && {
      key: "metricas",
      icon: <i className="bi bi-bar-chart-line"></i>,
      name: "Métricas",
      isActive: location.pathname === `/dashboard/${restaurante.slug}/metricas`,
      onClick: () => navigateAndClose(`/dashboard/${restaurante.slug}/metricas`),
    },
    permisos.canViewBitacora && {
      key: "bitacora",
      icon: <i className="bi bi-clock-history"></i>,
      name: "Bitácora",
      isActive: location.pathname === "/historial",
      onClick: () => navigateAndClose("/historial"),
    },
    restauranteSlug && {
      key: "web",
      icon: <i className="bi bi-globe"></i>,
      name: "Mi página web",
      isActive: false,
      onClick: openPageAndClose,
    },
    permisos.canAccessConfiguracion && {
      key: "configuracion",
      icon: <i className="bi bi-gear"></i>,
      name: "Configuraciones",
      isActive: location.pathname === `/dashboard/${restaurante.slug}/configuracion`,
      onClick: () => navigateAndClose(`/dashboard/${restaurante.slug}/configuracion`),
    },
  ].filter(Boolean);

  const renderMenuItems = () =>
    menuItems.map((item) => (
      <li className="nav-item" key={item.key}>
        <ButtonMain
          icon={item.icon}
          name={item.name}
          className={item.isActive ? "is-active" : ""}
          onClick={item.onClick}
        />
      </li>
    ));

    return(
        <section className="menu-main">
            <div className="mobile-menu-header">
                <button
                  className="mobile-menu-toggle"
                  type="button"
                  aria-label="Abrir menú"
                  aria-expanded={mobileMenuOpen}
                  onClick={() => setMobileMenuOpen(true)}
                >
                  <span></span>
                  <span></span>
                  <span></span>
                </button>
                <div className="mobile-menu-brand">
                    <img src={logoMobile} alt="Logo-menu" />
                </div>
                <div className="mobile-menu-logout">
                    <ButtonLogout
                        icon={<i className="bi bi-box-arrow-right"></i>}
                        name="Cerrar sesión"
                    />
                </div>
            </div>

            <div className="div-logo desktop-menu-logo">
                <img src={logo} alt="Logo-menu" />
            </div>
            <ul className="nav flex-column desktop-menu-nav">
                {renderMenuItems()}
            </ul>
            <div className="div-cerrar-sesion desktop-menu-logout">
                <ButtonLogout
                    icon={<i className="bi bi-box-arrow-right"></i>}
                    name="Cerrar sesión">
                </ButtonLogout>         
            </div>

            {mobileMenuOpen && (
              <button
                className="mobile-drawer-backdrop"
                type="button"
                aria-label="Cerrar menú"
                onClick={closeMobileMenu}
              />
            )}

            <aside className={`mobile-menu-drawer ${mobileMenuOpen ? "is-open" : ""}`} aria-hidden={!mobileMenuOpen}>
                <div className="mobile-drawer-header">
                    <img src={logoMobile} alt="Logo-menu" />
                    <button
                      className="mobile-drawer-close"
                      type="button"
                      aria-label="Cerrar menú"
                      onClick={closeMobileMenu}
                    >
                      <i className="bi bi-x-lg"></i>
                    </button>
                </div>
                <ul className="nav flex-column mobile-drawer-nav">
                    {renderMenuItems()}
                </ul>
                <div className="mobile-drawer-logout">
                    <ButtonLogout
                        icon={<i className="bi bi-box-arrow-right"></i>}
                        name="Cerrar sesión"
                    />
                </div>
            </aside>
        </section>
    );
}
