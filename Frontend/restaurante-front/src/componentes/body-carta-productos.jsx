import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/dashboard.css";
import "../styles/CartaProductos.css";
import ButtonCategoria from "../componentes/btn-categorias";
import CardsProductos from "../componentes/card-productos";
import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { authFetch } from "../api";
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

  if (loading) {
    return <p>Cargando dashboard...</p>;
  }

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  if (!data) {
    return <p>No hay datos disponibles</p>;
  }

  const { productos, categorias, categorias_todas, usuario } = data;
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
    });

  const productosPorPagina = 8;
  const totalPaginas = Math.ceil(productosFiltrados.length / productosPorPagina);

  const indiceUltimoProducto = paginaActual * productosPorPagina;
  const indicePrimerProducto = indiceUltimoProducto - productosPorPagina;

  const productosActuales = productosFiltrados.slice(
    indicePrimerProducto,
    indiceUltimoProducto
  );

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
};;
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

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || data.detail || "No se pudo eliminar el producto");
      }

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
    return(
                <section className="body-main">
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
                    
        
                    <div className="contenido-cards">
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
                          categoria={
                            typeof p.categoria === "string"
                              ? p.categoria
                              : p.categoria?.nombre
                          }
                          disponible={p.disponible}
                          destacado={p.destacado}
                          deleting={deletingId === p.id}
                          canManage={permisos.canManageProductos}
                          onDelete={permisos.canManageProductos ? handleDeleteProducto : null}
                          onEdit={permisos.canManageProductos ? (id) => navigate(`/carta-productos/${slug}/editar/${id}`) : null}
                        />
                      ))
                      )}
                    </div>
        
                    <div className="section-paginations-info">
                      <div className="div-info-paginacion">
                        <p>
                          Mostrando {productosFiltrados.length === 0 ? 0 : indicePrimerProducto + 1} a{" "}
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
