import { useEffect, useMemo, useState } from "react";
import MainMenu from "../componentes/Main-menu";
import "../styles/Historial.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import { authFetch } from "../api";

const DESKTOP_PAGE_SIZE = 20;
const MOBILE_PAGE_SIZE = 5;

export default function Historial() {
  const [historial, setHistorial] = useState([]);
  const [busqueda, setBusqueda] = useState("");
  const [filtro, setFiltro] = useState("TODOS");
  const [paginaActual, setPaginaActual] = useState(1);
  const [isMobile, setIsMobile] = useState(false);
  const [totalHistorial, setTotalHistorial] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const pageSize = isMobile ? MOBILE_PAGE_SIZE : DESKTOP_PAGE_SIZE;
  const backendPage =
    Math.floor(((paginaActual - 1) * pageSize) / DESKTOP_PAGE_SIZE) + 1;
  const indiceInicioBackend =
    ((paginaActual - 1) * pageSize) % DESKTOP_PAGE_SIZE;
  const totalPaginas = Math.max(1, Math.ceil(totalHistorial / pageSize));
  const hayPaginaAnterior = paginaActual > 1;
  const hayPaginaSiguiente = paginaActual < totalPaginas;

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 768px)");

    const actualizarVista = () => {
      const mobile = mediaQuery.matches;

      setIsMobile((actual) => {
        if (actual !== mobile) {
          setPaginaActual(1);
        }

        return mobile;
      });
    };

    actualizarVista();
    mediaQuery.addEventListener("change", actualizarVista);

    return () => {
      mediaQuery.removeEventListener("change", actualizarVista);
    };
  }, []);

  useEffect(() => {
    const cargarHistorial = async () => {
      const token = localStorage.getItem("access");

      if (!token) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError("");

        const response = await authFetch(`/historial/?page=${backendPage}`, {
          method: "GET",
        });

        if (!response.ok) {
          setError("Ocurrió un error al cargar la bitácora");
          return;
        }

        const data = await response.json();
        setHistorial(data.results || data);
        setTotalHistorial(data.count ?? (Array.isArray(data) ? data.length : 0));
      } catch {
        setHistorial([]);
        setTotalHistorial(0);
        setError("Ocurrió un error al cargar la bitácora");
      } finally {
        setLoading(false);
      }
    };

    cargarHistorial();
  }, [backendPage]);

  useEffect(() => {
    if (paginaActual > totalPaginas) {
      setPaginaActual(totalPaginas);
    }
  }, [paginaActual, totalPaginas]);

  const historialFiltrado = useMemo(() => {
    return historial.filter((item) => {
      const coincideBusqueda =
        item.producto.toLowerCase().includes(busqueda.toLowerCase()) ||
        item.descripcion.toLowerCase().includes(busqueda.toLowerCase());

      const coincideFiltro =
        filtro === "TODOS" || item.accion === filtro;

      return coincideBusqueda && coincideFiltro;
    });
  }, [historial, busqueda, filtro]);

  const historialPagina = useMemo(() => {
    if (!isMobile) {
      return historialFiltrado;
    }

    return historialFiltrado.slice(
      indiceInicioBackend,
      indiceInicioBackend + pageSize
    );
  }, [historialFiltrado, indiceInicioBackend, isMobile, pageSize]);

  const handleBusquedaChange = (event) => {
    setBusqueda(event.target.value);
    setPaginaActual(1);
  };

  const handleFiltroChange = (nuevoFiltro) => {
    setFiltro(nuevoFiltro);
    setPaginaActual(1);
  };

  const colorAccion = (accion) => {
    if (accion === "CREADO") return "accion-creado";
    if (accion === "ELIMINADO") return "accion-eliminado";
    if (accion === "EDITADO") return "accion-editado";
    return "accion-default";
  };

  return (
    <div className="body historial-shell">
      <main className="container-fluid historial-main" id="main">
        <MainMenu/>

        <section className="historial-page">
          <header className="historial-header">
            <div>
              <h1>Bitácora</h1>
            </div>

            <div className="historial-breadcrumb">
              <span>Inicio</span>
              <span>{">"}</span>
              <strong>Bitácora</strong>
            </div>
          </header>

          <div className="historial-actions">
            <div className="historial-search">
              <i className="bi bi-search"></i>
              <input
                type="text"
                placeholder="Buscar producto..."
                value={busqueda}
                onChange={handleBusquedaChange}
              />
            </div>
          </div>

          <div className="historial-tabs">
            <button
              className={filtro === "TODOS" ? "active" : ""}
              onClick={() => handleFiltroChange("TODOS")}
            >
              <i className="bi bi-grid"></i>
              Todos
            </button>

            <button
              className={filtro === "EDITADO" ? "active" : ""}
              onClick={() => handleFiltroChange("EDITADO")}
            >
              Editado
            </button>

            <button
              className={filtro === "ELIMINADO" ? "active" : ""}
              onClick={() => handleFiltroChange("ELIMINADO")}
            >
              Eliminado
            </button>

            <button
              className={filtro === "CREADO" ? "active" : ""}
              onClick={() => handleFiltroChange("CREADO")}
            >
              Creado
            </button>
          </div>

          <div className="historial-table-wrapper">
            {loading ? (
              <div className="historial-empty">Cargando...</div>
            ) : error ? (
              <div className="alert alert-danger">{error}</div>
            ) : historialPagina.length > 0 ? (
              <div className="historial-list">
                {historialPagina.map((item) => (
                  <div key={item.id} className="historial-row">
                    <span className={`estado-dot ${colorAccion(item.accion)}`}></span>

                    <div className="historial-col">
                      <strong>Acción:</strong>
                      <p>{item.accion}</p>
                    </div>

                    <div className="historial-col">
                      <strong>Producto:</strong>
                      <p>{item.producto}</p>
                    </div>

                    <div className="historial-col descripcion">
                      <strong>Detalle:</strong>
                      <p>{item.descripcion}</p>
                    </div>

                    <div className="historial-col">
                      <strong>Responsable:</strong>
                      <p>{item.usuario}</p>
                    </div>

                    <div className="historial-col fecha">
                      <strong>Fecha Actualización:</strong>
                      <p>{new Date(item.fecha).toLocaleDateString("es-CL")}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="historial-empty">
                No hay registros en la bitácora.
              </div>
            )}
          </div>

          <footer className="table-footer">
            <span>
              Página {paginaActual} · Mostrando {historialPagina.length} de {totalHistorial} registros
            </span>
            <div className="paginations">
              <button
                type="button"
                disabled={!hayPaginaAnterior}
                onClick={() => setPaginaActual((page) => Math.max(1, page - 1))}
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={!hayPaginaSiguiente}
                onClick={() => setPaginaActual((page) => page + 1)}
              >
                Siguiente
              </button>
            </div>
          </footer>
        </section>
      </main>
    </div>
  );
}

