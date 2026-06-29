import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import logoMenly from "../../assets/logoMenly2.png";

const navItems = [
  { label: "Funciones", href: "#funciones" },
  { label: "Planes", href: "#planes" },
  { label: "Diseño Web", href: "#diseno-web" },
  { label: "Recursos", href: "#recursos" },
  { label: "Contacto", href: "#contacto" },
];

const LOGIN_URL = "https://menly.cl/";
export default function PublicNavbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    document.body.classList.toggle("public-menu-open", menuOpen);

    return () => {
      document.body.classList.remove("public-menu-open");
    };
  }, [menuOpen]);

  const closeMenu = () => setMenuOpen(false);
  const handleSectionClick = (event, href) => {
    const section = document.querySelector(href);

    if (!section) {
      event.preventDefault();
      if (href === "#planes") {
        navigate("/planes");
        closeMenu();
        return;
      }
      navigate(`/saber-mas${href}`);
      closeMenu();
      return;
    }

    event.preventDefault();
    section.scrollIntoView({ behavior: "smooth", block: "start" });
    window.history.replaceState(null, "", href);
    closeMenu();
  };

  return (
    <header className="public-navbar">
      <Link className="public-navbar__brand" to="/" aria-label="Menly inicio" onClick={closeMenu}>
        <img src={logoMenly} alt="Menly" />
      </Link>

      <button
        type="button"
        className="public-navbar__toggle"
        aria-label={menuOpen ? "Cerrar menú" : "Abrir menú"}
        aria-expanded={menuOpen}
        aria-controls="public-navbar-menu"
        onClick={() => setMenuOpen((open) => !open)}
      >
        <span aria-hidden="true"></span>
        <span aria-hidden="true"></span>
        <span aria-hidden="true"></span>
      </button>

      <div
        className={`public-navbar__menu ${menuOpen ? "is-open" : ""}`}
        id="public-navbar-menu"
      >
        <nav className="public-navbar__links" aria-label="Navegación principal">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              onClick={(event) => handleSectionClick(event, item.href)}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="public-navbar__actions">
          <a className="public-navbar__login" href={LOGIN_URL} onClick={closeMenu}>
            Iniciar sesión
          </a>
          <Link
            className="public-navbar__demo"
            to="/planes"
            onClick={closeMenu}
          >
            Solicitar demo
          </Link>
        </div>
      </div>
    </header>
  );
}
