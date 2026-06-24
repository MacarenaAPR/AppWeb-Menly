import { useEffect, useMemo, useState } from "react";
import MainMenu from "../componentes/Main-menu";
import "../styles/Historial.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import { authFetch } from "../api";

const DESKTOP_PAGE_SIZE = 20;
const MOBILE_PAGE_SIZE = 5;
const ESTADOS_PEDIDO = ["pendiente", "confirmado", "en_preparacion", "listo", "entregado", "cancelado", "completado"];
const estadoPedidoLabels = {
  pendiente: "Pendiente",
  confirmado: "Confirmado",
  en_preparacion: "En preparación",
  listo: "Listo",
  entregado: "Entregado",
  cancelado: "Cancelado",
  completado: "Completado",
};

const formatearMoneda = (valor) =>
  new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(Number(valor || 0));

const totalProductosPedido = (items = []) =>
  items.reduce((total, item) => total + Number(item?.cantidad || 0), 0);

export default function Historial() {
  const [panelActivo, setPanelActivo] = useState("movimientos");
  const [historial, setHistorial] = useState([]);
  const [pedidos, setPedidos] = useState([]);
  const [busqueda, setBusqueda] = useState("");
  const [filtro, setFiltro] = useState("TODOS");
  const [filtroEstadoPedido, setFiltroEstadoPedido] = useState("todos");
  const [fechaDesdePedido, setFechaDesdePedido] = useState("");
  const [fechaHastaPedido, setFechaHastaPedido] = useState("");
  const [pedidoDetalle, setPedidoDetalle] = useState(null);
  const [movimientoDetalle, setMovimientoDetalle] = useState(null);
  const [paginaActual, setPaginaActual] = useState(1);
  const [isMobile, setIsMobile] = useState(false);
  const [totalHistorial, setTotalHistorial] = useState(0);
  const [totalPedidos, setTotalPedidos] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const pageSize = isMobile ? MOBILE_PAGE_SIZE : DESKTOP_PAGE_SIZE;
  const backendPage =
    Math.floor(((paginaActual - 1) * pageSize) / DESKTOP_PAGE_SIZE) + 1;
  const indiceInicioBackend =
    ((paginaActual - 1) * pageSize) % DESKTOP_PAGE_SIZE;
  const totalActual = panelActivo === "movimientos" ? totalHistorial : totalPedidos;
  const totalPaginas = Math.max(1, Math.ceil(totalActual / pageSize));
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

    if (panelActivo === "movimientos") {
      cargarHistorial();
    }
  }, [backendPage, panelActivo]);

  useEffect(() => {
    const cargarPedidos = async () => {
      const token = localStorage.getItem("access");

      if (!token) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError("");

        const params = new URLSearchParams({
          page: String(paginaActual),
          page_size: String(pageSize),
        });

        if (busqueda.trim()) params.set("search", busqueda.trim());
        if (filtroEstadoPedido !== "todos") params.set("estado", filtroEstadoPedido);
        if (fechaDesdePedido) params.set("fecha_desde", fechaDesdePedido);
        if (fechaHastaPedido) params.set("fecha_hasta", fechaHastaPedido);

        const response = await authFetch(`/historial/pedidos/?${params.toString()}`, {
          method: "GET",
        });

        if (!response.ok) {
          setError("Ocurrió un error al cargar el historial de pedidos");
          return;
        }

        const data = await response.json();
        setPedidos(data.results || data);
        setTotalPedidos(data.count ?? (Array.isArray(data) ? data.length : 0));
      } catch {
        setPedidos([]);
        setTotalPedidos(0);
        setError("Ocurrió un error al cargar el historial de pedidos");
      } finally {
        setLoading(false);
      }
    };

    if (panelActivo === "pedidos") {
      cargarPedidos();
    }
  }, [busqueda, fechaDesdePedido, fechaHastaPedido, filtroEstadoPedido, pageSize, paginaActual, panelActivo]);

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

  const handlePanelChange = (panel) => {
    setPanelActivo(panel);
    setBusqueda("");
    setPaginaActual(1);
    setError("");
  };

  const handleFiltroChange = (nuevoFiltro) => {
    setFiltro(nuevoFiltro);
    setPaginaActual(1);
  };

  const handleFiltroPedidoChange = (nuevoFiltro) => {
    setFiltroEstadoPedido(nuevoFiltro);
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

          <div className="historial-panel-tabs">
            <button
              className={panelActivo === "movimientos" ? "active" : ""}
              onClick={() => handlePanelChange("movimientos")}
            >
              <i className="bi bi-activity"></i>
              Bitácora de movimientos
            </button>
            <button
              className={panelActivo === "pedidos" ? "active" : ""}
              onClick={() => handlePanelChange("pedidos")}
            >
              <i className="bi bi-receipt"></i>
              Bitácora de pedidos
            </button>
          </div>

          <select
            className="mobile-menly-select historial-mobile-panel-select"
            value={panelActivo}
            onChange={(event) => handlePanelChange(event.target.value)}
            aria-label="Seleccionar sección de bitácora"
          >
            <option value="movimientos">Bitácora de movimientos</option>
            <option value="pedidos">Bitácora de pedidos</option>
          </select>

          <div className="historial-actions">
            <div className="historial-search">
              <i className="bi bi-search"></i>
              <input
                type="text"
                placeholder={panelActivo === "movimientos" ? "Buscar producto..." : "Buscar cliente, teléfono o N° pedido..."}
                value={busqueda}
                onChange={handleBusquedaChange}
              />
            </div>
          </div>

          {panelActivo === "movimientos" ? (
            <>
              <select
                className="mobile-menly-select historial-mobile-filter-select"
                value={filtro}
                onChange={(event) => handleFiltroChange(event.target.value)}
                aria-label="Filtrar movimientos"
              >
                <option value="TODOS">Todos</option>
                <option value="EDITADO">Editado</option>
                <option value="ELIMINADO">Eliminado</option>
                <option value="CREADO">Creado</option>
              </select>

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
            </>
          ) : (
            <div className="historial-pedidos-filters">
              <select
                value={filtroEstadoPedido}
                onChange={(event) => handleFiltroPedidoChange(event.target.value)}
              >
                <option value="todos">Todos los estados</option>
                {ESTADOS_PEDIDO.map((estado) => (
                  <option key={estado} value={estado}>
                    {estadoPedidoLabels[estado] || estado}
                  </option>
                ))}
              </select>
              <input
                type="date"
                value={fechaDesdePedido}
                onChange={(event) => {
                  setFechaDesdePedido(event.target.value);
                  setPaginaActual(1);
                }}
              />
              <input
                type="date"
                value={fechaHastaPedido}
                onChange={(event) => {
                  setFechaHastaPedido(event.target.value);
                  setPaginaActual(1);
                }}
              />
            </div>
          )}

          <div className="historial-table-wrapper">
            {loading ? (
              <div className="historial-empty">Cargando...</div>
            ) : error ? (
              <div className="alert alert-danger">{error}</div>
            ) : panelActivo === "movimientos" && historialPagina.length > 0 ? (
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
                      <button
                        className="historial-detail-btn historial-eye-btn"
                        type="button"
                        onClick={() => setMovimientoDetalle(item)}
                        aria-label={`Ver detalle de ${item.producto}`}
                      >
                        <i className="bi bi-eye"></i>
                        Ver
                      </button>
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
            ) : panelActivo === "pedidos" && pedidos.length > 0 ? (
              <div className="historial-list historial-pedidos-list">
                {pedidos.map((pedido) => (
                  <div key={pedido.id} className="historial-row historial-pedido-row">
                    <div className="historial-col">
                      <strong>N° pedido:</strong>
                      <p>#{pedido.numero_pedido}</p>
                    </div>

                    <div className="historial-col">
                      <strong>Cliente:</strong>
                      <p>{pedido.nombre_cliente}</p>
                    </div>

                    <div className="historial-col">
                      <strong>Total:</strong>
                      <p>{formatearMoneda(pedido.total)}</p>
                    </div>

                    <div className="historial-col">
                      <strong>Estado:</strong>
                      <p>{estadoPedidoLabels[pedido.estado] || pedido.estado}</p>
                    </div>

                    <button
                      className="historial-detail-btn"
                      type="button"
                      onClick={() => setPedidoDetalle(pedido)}
                    >
                      <i className="bi bi-eye"></i>
                      Ver detalle
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="historial-empty">
                {panelActivo === "movimientos"
                  ? "No hay registros en la bitácora."
                  : "No hay pedidos anteriores en la bitácora."}
              </div>
            )}
          </div>

          <footer className="table-footer">
            <span>
              Página {paginaActual} · Mostrando {panelActivo === "movimientos" ? historialPagina.length : pedidos.length} de {totalActual} registros
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

          {pedidoDetalle && (
            <div className="historial-modal-bg" onClick={() => setPedidoDetalle(null)}>
              <div className="historial-modal" onClick={(event) => event.stopPropagation()}>
                <header>
                  <div>
                    <p>Pedido WhatsApp</p>
                    <h2>#{pedidoDetalle.numero_pedido}</h2>
                  </div>
                  <button type="button" onClick={() => setPedidoDetalle(null)}>
                    <i className="bi bi-x-lg"></i>
                  </button>
                </header>

                <div className="historial-modal-grid">
                  <p><strong>Cliente:</strong> {pedidoDetalle.nombre_cliente}</p>
                  <p><strong>Teléfono:</strong> {pedidoDetalle.telefono_cliente}</p>
                  <p><strong>Fecha:</strong> {new Date(pedidoDetalle.fecha_creacion).toLocaleString("es-CL")}</p>
                  <p><strong>Entrega:</strong> {pedidoDetalle.tipo_entrega_display || pedidoDetalle.tipo_entrega}</p>
                  {pedidoDetalle.direccion_entrega && (
                    <p><strong>Dirección:</strong> {pedidoDetalle.direccion_entrega}</p>
                  )}
                  <p><strong>Estado:</strong> {estadoPedidoLabels[pedidoDetalle.estado] || pedidoDetalle.estado}</p>
                  <p><strong>Total:</strong> {formatearMoneda(pedidoDetalle.total)}</p>
                  <p><strong>Productos:</strong> {totalProductosPedido(pedidoDetalle.productos_snapshot)} productos</p>
                  {pedidoDetalle.whatsapp_destino && (
                    <p><strong>WhatsApp destino:</strong> {pedidoDetalle.whatsapp_destino}</p>
                  )}
                </div>

                <div className="historial-modal-items">
                  {(pedidoDetalle.productos_snapshot || []).map((item, index) => (
                    <div key={`${item.nombre}-${index}`}>
                      <strong>{item.cantidad} x {item.nombre}</strong>
                      <span>{formatearMoneda(item.subtotal ?? (Number(item.precio_unitario || 0) * Number(item.cantidad || 0)))}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {movimientoDetalle && (
            <div className="historial-modal-bg" onClick={() => setMovimientoDetalle(null)}>
              <div className="historial-modal" onClick={(event) => event.stopPropagation()}>
                <header>
                  <div>
                    <p>Movimiento</p>
                    <h2>{movimientoDetalle.accion}</h2>
                  </div>
                  <button type="button" onClick={() => setMovimientoDetalle(null)}>
                    <i className="bi bi-x-lg"></i>
                  </button>
                </header>

                <div className="historial-modal-grid">
                  <p><strong>Acción:</strong> {movimientoDetalle.accion}</p>
                  <p><strong>Producto/entidad afectada:</strong> {movimientoDetalle.producto}</p>
                  <p><strong>Responsable:</strong> {movimientoDetalle.usuario}</p>
                  <p><strong>Fecha de actualización:</strong> {new Date(movimientoDetalle.fecha).toLocaleString("es-CL")}</p>
                </div>

                <div className="historial-modal-detail">
                  <strong>Detalle completo</strong>
                  <p>{movimientoDetalle.descripcion}</p>
                </div>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

