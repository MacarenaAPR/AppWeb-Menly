import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/dashboard.css";
import "../styles/CartaProductos.css";
import ButtonCategoria from "../componentes/btn-categorias";
import CardsProductos from "../componentes/card-productos";
import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { authFetch, readJsonResponse } from "../api";
import { permisosPorRol } from "../utils/permisos";

export default function CartaProducto(){
  const [busqueda, setBusqueda] = useState("");

  const [data, setData] = useState(null);
  const [paginaActual, setPaginaActual] = useState(1);
  const [categoriaActiva, setCategoriaActiva] = useState("Todos");
  const [estadoCategoria] = useState("activas");

  const { slug } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleteMessage, setDeleteMessage] = useState("");
  const [deletingId, setDeletingId] = useState(null);
  const navigate = useNavigate();
  const scrollRef = useRef(null);
  const [productosPorPagina, setProductosPorPagina] = useState(8);
  const [filtroDisponibilidad, setFiltroDisponibilidad] = useState("todos");
  const [viewMode, setViewMode] = useState(() => {
    const savedMode = window.localStorage.getItem("carta-productos-view-mode");

    if (savedMode === "cards" || savedMode === "list") {
      return savedMode;
    }

    return "cards";
  });

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

        const result = await readJsonResponse(
          response,
          "/mi-restaurante/",
          "Error al cargar datos"
        );

        if (slug !== result.restaurante.slug) {
          navigate(`/carta-productos/${result.restaurante.slug}`, { replace: true });
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

  const productos = data?.productos || [];
  const categorias = data?.categorias || [];
  const categorias_todas = data?.categorias_todas;
  const usuario = data?.usuario;
  const permisos = permisosPorRol(usuario?.rol);
  const categoriasBase = categorias_todas || categorias;
  const categoriasFiltradas = categoriasBase.filter((cat) => {
    if (estadoCategoria === "activas") return cat.activa !== false;
    if (estadoCategoria === "inactivas") return cat.activa === false;
    return true;
  });

  const categoriasBotones = [
    "Todos",
    ...categoriasFiltradas.map((cat) => cat.nombre)
  ];

  const productosFiltrados = productos
    .filter((p) => {
      if (typeof p.categoria === "object" && p.categoria !== null) {
        return p.categoria.activa !== false;
      }

      return true;
    })
    .filter((p) => {
      // filtro por categoría
      if (categoriaActiva === "Todos") return true;

      if (typeof p.categoria === "string") {
        return p.categoria === categoriaActiva;
      }

      if (typeof p.categoria === "object" && p.categoria !== null) {
        return p.categoria.nombre === categoriaActiva;
      }

      return false;
    })
    .filter((p) => {
      // filtro por búsqueda
      if (!busqueda) return true;

      const texto = busqueda.toLowerCase();

      const nombre = p.nombre?.toLowerCase() || "";

      const categoria =
        typeof p.categoria === "string"
          ? p.categoria.toLowerCase()
          : p.categoria?.nombre?.toLowerCase() || "";

      const precio = p.precio?.toString() || "";

      return (
        nombre.includes(texto) ||
        categoria.includes(texto) ||
        precio.includes(texto)
      );
    })
    .filter((p) => {
      if (filtroDisponibilidad === "disponibles") {
        return p.disponible !== false;
      }

      if (filtroDisponibilidad === "no_disponibles") {
        return p.disponible === false;
      }

      return true;
    });

  const totalPaginas =
    productosFiltrados.length === 0
      ? 0
      : Math.ceil(productosFiltrados.length / productosPorPagina);

  const indiceInicio = (paginaActual - 1) * productosPorPagina;
  const indiceUltimoProducto = indiceInicio + productosPorPagina;

  const productosActuales = productosFiltrados.slice(
    indiceInicio,
    indiceInicio + productosPorPagina
  );

  useEffect(() => {
    const updateProductosPorPagina = () => {
      if (window.innerWidth <= 768) {
        setProductosPorPagina(10);
      } 
      else if (window.innerWidth <= 973) {
        setProductosPorPagina(6);}
      else if (window.innerWidth <= 1118) {
        setProductosPorPagina(4);}
      else if (window.innerWidth <= 1391) {
        setProductosPorPagina(6);}
      else if (window.innerWidth >= 1664) {
        setProductosPorPagina(10);
      } else {
        setProductosPorPagina(8);
      }
    };

    updateProductosPorPagina();
    window.addEventListener("resize", updateProductosPorPagina);

    return () => {
      window.removeEventListener("resize", updateProductosPorPagina);
    };
  }, []);

  useEffect(() => {
    if (totalPaginas > 0 && paginaActual > totalPaginas) {
      setPaginaActual(totalPaginas);
    }
  }, [paginaActual, totalPaginas]);

  useEffect(() => {
    window.localStorage.setItem("carta-productos-view-mode", viewMode);
  }, [viewMode]);

  if (loading) {
    return <p>Cargando dashboard...</p>;
  }

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  if (!data) {
    return <p>No hay datos disponibles</p>;
  }

  const handleCategoriaClick = (categoria) => {
    setCategoriaActiva(categoria);
    setPaginaActual(1);
  };

  const renderPaginas = () => {
    const pages = [];

    if (totalPaginas <= 7) {
      for (let i = 1; i <= totalPaginas; i++) {
        pages.push(i);
      }
    } else {
      pages.push(1);

      if (paginaActual > 3) {
        pages.push("...");
      }

      for (
        let i = Math.max(2, paginaActual - 1);
        i <= Math.min(totalPaginas - 1, paginaActual + 1);
        i++
      ) {
        pages.push(i);
      }

      if (paginaActual < totalPaginas - 2) {
        pages.push("...");
      }

      pages.push(totalPaginas);
    }

    return pages;
  };


  const scroll = (dir) => {
  if (!scrollRef.current) return;

  scrollRef.current.scrollBy({
    left: dir === "left" ? -200 : 200,
    behavior: "smooth",
  });
};
  const handleDeleteProducto = async (id) => {
    const confirmar = window.confirm("¿Seguro que quieres eliminar este producto?");
    if (!confirmar) return;

    try {
      setDeletingId(id);
      setDeleteMessage("");
      setError("");

      const response = await authFetch(`/mi-restaurante/productos/${id}/eliminar/`, {
        method: "DELETE",
      });

      const data = await readJsonResponse(
        response,
        `/mi-restaurante/productos/${id}/eliminar/`,
        "No se pudo eliminar el producto"
      );

      setData((prevData) => ({
        ...prevData,
        productos: prevData.productos.filter((producto) => producto.id !== id),
      }));
      setDeleteMessage(data.message || "Producto eliminado correctamente");
    } catch (error) {
      setError(error.message || "No se pudo eliminar el producto");
    } finally {
      setDeletingId(null);
    }
  };

  const handleDestacadoProducto = (id, destacado) => {
    setData((prevData) => {
      if (!prevData?.productos) return prevData;

      return {
        ...prevData,
        productos: prevData.productos.map((producto) =>
          producto.id === id ? { ...producto, destacado } : producto
        ),
      };
    });
  };

    return(
                <section className="body-main carta-productos-page">
                  <header className="body-header">
                    <div className="header-name-search">
                      <h1>Carta / Productos</h1>
        
                      <div className="div-input-search">
                        <span className="input-group-text">
                          <i className="bi bi-search"></i>
                        </span>
                        <input
                          className="form-control form-control-sm"
                          id="form-control"
                          type="text"
                          placeholder="Buscar producto..."
                          value={busqueda}
                          onChange={(e) => {
                            setBusqueda(e.target.value);
                            setPaginaActual(1); // reset página al buscar
                          }}
                        />
                      </div>
                    </div>
        
                    <div className="header-add-seguimiento">
                      <div className="div-seguimiento">
                        <a href="">Inicio</a>
                        <span>{" > "}</span>
                        <a className="a-active" href="">
                          Carta / Productos
                        </a>
                      </div>
        
                      {permisos.canManageProductos && (
                      <button
                        className="btn-add"
                        onClick={() => navigate(`/carta-add/${slug}`)}
                      >
                        <i className="bi bi-plus"></i> Agregar Producto
                      </button>
                      )}
                    </div>
                  </header>
        
                    <div className="body-contenido">
                    {deleteMessage && <p className="text-success">{deleteMessage}</p>}
                    
                    <div className="div-categorias">
                      <button className="button-arrow" onClick={() => scroll("left")}>{"<"}</button>
                      <div ref={scrollRef} className="div-filtros-categorias">
                        {categoriasBotones.map((cat) => (
                          <ButtonCategoria
                            key={cat}
                            name={cat}
                            icon={cat === "Todos" ? "bi-grid" : null}
                            active={categoriaActiva === cat}
                            onClick={() => handleCategoriaClick(cat)}
                          />
                        ))}
                      </div>
                      <button className="button-arrow" onClick={() => scroll("right")}>{">"}</button>
                    </div>

                    <div className="carta-productos-mobile-search">
                      <div className="div-input-search">
                        <span className="input-group-text">
                          <i className="bi bi-search"></i>
                        </span>
                        <input
                          className="form-control form-control-sm"
                          type="text"
                          placeholder="Buscar producto..."
                          value={busqueda}
                          onChange={(e) => {
                            setBusqueda(e.target.value);
                            setPaginaActual(1);
                          }}
                        />
                      </div>
                    </div>

                    <div className="carta-productos-toolbar">
                      <div className="carta-productos-mobile-selects">
                        <select
                          className="mobile-menly-select"
                          value={viewMode}
                          onChange={(event) => setViewMode(event.target.value)}
                          aria-label="Seleccionar vista de productos"
                        >
                          <option value="cards">Tarjetas</option>
                          <option value="list">Lista</option>
                        </select>

                        <select
                          className="mobile-menly-select"
                          value={filtroDisponibilidad}
                          onChange={(event) => {
                            setFiltroDisponibilidad(event.target.value);
                            setPaginaActual(1);
                          }}
                          aria-label="Filtrar por disponibilidad"
                        >
                          <option value="todos">Todos</option>
                          <option value="disponibles">Disponibles</option>
                          <option value="no_disponibles">No disponibles</option>
                        </select>
                      </div>

                      <div className="view-mode-toggle" aria-label="Cambiar vista de productos">
                        <button
                          type="button"
                          className={viewMode === "cards" ? "active" : ""}
                          aria-pressed={viewMode === "cards"}
                          onClick={() => setViewMode("cards")}
                        >
                          <i className="bi bi-grid-3x3-gap"></i>
                          Tarjetas
                        </button>

                        <button
                          type="button"
                          className={viewMode === "list" ? "active" : ""}
                          aria-pressed={viewMode === "list"}
                          onClick={() => setViewMode("list")}
                        >
                          <i className="bi bi-list-ul"></i>
                          Lista
                        </button>
                      </div>

                      <div className="availability-filter-toggle" aria-label="Filtrar productos por disponibilidad">
                        <button
                          type="button"
                          className={filtroDisponibilidad === "todos" ? "active" : ""}
                          aria-pressed={filtroDisponibilidad === "todos"}
                          onClick={() => {
                            setFiltroDisponibilidad("todos");
                            setPaginaActual(1);
                          }}
                        >
                          Todos
                        </button>

                        <button
                          type="button"
                          className={filtroDisponibilidad === "disponibles" ? "active" : ""}
                          aria-pressed={filtroDisponibilidad === "disponibles"}
                          onClick={() => {
                            setFiltroDisponibilidad("disponibles");
                            setPaginaActual(1);
                          }}
                        >
                          Disponibles
                        </button>

                        <button
                          type="button"
                          className={filtroDisponibilidad === "no_disponibles" ? "active" : ""}
                          aria-pressed={filtroDisponibilidad === "no_disponibles"}
                          onClick={() => {
                            setFiltroDisponibilidad("no_disponibles");
                            setPaginaActual(1);
                          }}
                        >
                          No disponibles
                        </button>
                      </div>
                    </div>
                    

                    <div className={`contenido-cards ${viewMode === "list" ? "is-list" : "is-cards"}`}>
                      <span className="carta-productos-heading carta-productos-heading-categoria">Categoría</span>
                      <span className="carta-productos-heading carta-productos-heading-precio">Precio</span>
                      <span className="carta-productos-heading carta-productos-heading-disponible">Disponible</span>
                      <span className="carta-productos-heading carta-productos-heading-destacado">Destacado</span>
                      {productosActuales.length === 0 ? (
                        <p>No hay productos disponibles.</p>
                      ) : (
                      productosActuales.map((p) => (
                        <CardsProductos
                          key={p.id}
                          id={p.id}
                          img={p.imagen}
                          titulo={p.nombre}
                          price={p.precio}
                          descripcion={p.descripcion}
                          categoria={
                            typeof p.categoria === "string"
                              ? p.categoria
                              : p.categoria?.nombre
                          }
                          disponible={p.disponible}
                          destacado={p.destacado}
                          variantesCount={Array.isArray(p.variantes) ? p.variantes.length : 0}
                          isListView={viewMode === "list"}
                          isCardsView={viewMode === "cards"}
                          deleting={deletingId === p.id}
                          canManage={permisos.canManageProductos}
                          onDelete={permisos.canManageProductos ? handleDeleteProducto : null}
                          onEdit={permisos.canManageProductos ? (id) => navigate(`/carta-productos/${slug}/editar/${id}`) : null}
                          onDestacadoChange={handleDestacadoProducto}
                        />
                      ))
                      )}
                    </div>
        
                    <div className="section-paginations-info">
                      <div className="div-info-paginacion">
                        <p>
                          Mostrando {productosFiltrados.length === 0 ? 0 : indiceInicio + 1} a{" "}
                          {Math.min(indiceUltimoProducto, productosFiltrados.length)} de{" "}
                          {productosFiltrados.length} Productos
                        </p>
                      </div>
        
                      {totalPaginas > 0 && (
                        <div className="paginations">
                          <button
                            onClick={() => setPaginaActual(paginaActual - 1)}
                            disabled={paginaActual === 1}
                            className="arrow-btn"
                          >
                            <i className="bi bi-chevron-left"></i>
                          </button>
        
                          {renderPaginas().map((item, index) =>
                            item === "..." ? (
                              <span key={index} className="dots">
                                ...
                              </span>
                            ) : (
                              <button
                                key={index}
                                onClick={() => setPaginaActual(item)}
                                className={paginaActual === item ? "active" : ""}
                              >
                                {item}
                              </button>
                            )
                          )}
        
                          <button
                            onClick={() => setPaginaActual(paginaActual + 1)}
                            disabled={paginaActual === totalPaginas}
                            className="arrow-btn"
                          >
                            <i className="bi bi-chevron-right"></i>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </section>
    );
}
