import { useCallback, useEffect, useMemo, useState } from "react";
import "../styles/ReservasDashboard.css";
import MainMenu from "../componentes/Main-menu";
import { authFetch } from "../api";

const ESTADOS_PEDIDO = ["pendiente", "confirmado", "en_preparacion", "listo", "entregado", "cancelado"];

const estadoLabels = {
  pendiente: "Pendiente",
  confirmado: "Confirmado",
  en_preparacion: "En preparacion",
  listo: "Listo",
  entregado: "Entregado",
  cancelado: "Cancelado",
  completado: "Completado",
};

const formEspecialInicial = {
  nombre_cliente: "",
  telefono_cliente: "",
  email_cliente: "",
  descripcion_original: "",
  fecha_entrega: "",
  estado: "pendiente",
  items: [{ nombre: "", descripcion: "", cantidad: 1, precio_unitario: 0 }],
};

const obtenerMensajeError = async (response, fallback) => {
  try {
    const data = await response.json();
    if (typeof data === "string") return data;
    const valores = Object.values(data || {});
    return data?.error || data?.detail || valores.flat?.()?.[0] || fallback;
  } catch {
    return fallback;
  }
};

const formatearMoneda = (valor) =>
  new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(Number(valor || 0));

const formatearFecha = (valor) => {
  if (!valor) return "Sin fecha";
  return new Date(valor).toLocaleDateString("es-CL");
};

const resumenItems = (items = []) =>
  items.map((item) => `${item.cantidad} x ${item.nombre}`).join(", ");

export default function PedidosDashboard() {
  const [restaurante, setRestaurante] = useState(null);
  const [catalogoProductos, setCatalogoProductos] = useState([]);
  const [tabActiva, setTabActiva] = useState("");
  const [pedidosWhatsapp, setPedidosWhatsapp] = useState([]);
  const [pedidosEspeciales, setPedidosEspeciales] = useState([]);
  const [metricas, setMetricas] = useState({ whatsapp: {}, especiales: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [detalle, setDetalle] = useState(null);
  const [mostrarFormularioEspecial, setMostrarFormularioEspecial] = useState(false);
  const [pedidoEditando, setPedidoEditando] = useState(null);
  const [formEspecial, setFormEspecial] = useState(formEspecialInicial);
  const [detalleItems, setDetalleItems] = useState([]);
  const [productoBusqueda, setProductoBusqueda] = useState("");
  const [productoSeleccionado, setProductoSeleccionado] = useState("");
  const [cantidadProductoNuevo, setCantidadProductoNuevo] = useState(1);
  const [direccionDetalle, setDireccionDetalle] = useState("");

  const whatsappActivo = restaurante?.carrito_whatsapp_activo === true;
  const especialesActivo = restaurante?.solicitudes_especiales_activas === true;

  const tabsDisponibles = useMemo(() => {
    const tabs = [];
    if (whatsappActivo) tabs.push("whatsapp");
    if (especialesActivo) tabs.push("especiales");
    return tabs;
  }, [whatsappActivo, especialesActivo]);

  const cargarRestaurante = useCallback(async () => {
    const response = await authFetch("/mi-restaurante/", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(await obtenerMensajeError(response, "No se pudo cargar el restaurante."));
    }
    const data = await response.json();
    setRestaurante(data.restaurante);
    setCatalogoProductos((data.productos || []).filter((producto) => producto.disponible !== false));
    return data.restaurante;
  }, []);

  const cargarPedidos = useCallback(async (restauranteActual) => {
    if (!restauranteActual) return;

    const requests = [
      authFetch("/mi-restaurante/pedidos/metricas/"),
    ];

    if (restauranteActual.carrito_whatsapp_activo === true) {
      requests.push(authFetch("/mi-restaurante/pedidos/whatsapp/"));
    }

    if (restauranteActual.solicitudes_especiales_activas === true) {
      requests.push(authFetch("/mi-restaurante/pedidos/especiales/"));
    }

    const respuestas = await Promise.all(requests);
    const [metricasResponse, whatsappResponse, especialesResponse] = respuestas;

    if (!metricasResponse.ok) {
      throw new Error(await obtenerMensajeError(metricasResponse, "No se pudieron cargar las metricas."));
    }
    setMetricas(await metricasResponse.json());

    let indice = 1;
    if (restauranteActual.carrito_whatsapp_activo === true) {
      if (!whatsappResponse.ok) {
        throw new Error(await obtenerMensajeError(whatsappResponse, "No se pudieron cargar los pedidos WhatsApp."));
      }
      const data = await whatsappResponse.json();
      setPedidosWhatsapp(data.results || data);
      indice += 1;
    } else {
      setPedidosWhatsapp([]);
    }

    if (restauranteActual.solicitudes_especiales_activas === true) {
      const response = respuestas[indice];
      if (!response.ok) {
        throw new Error(await obtenerMensajeError(response, "No se pudieron cargar los pedidos especiales."));
      }
      const data = await response.json();
      setPedidosEspeciales(data.results || data);
    } else {
      setPedidosEspeciales([]);
    }
  }, []);

  useEffect(() => {
    const cargar = async () => {
      setLoading(true);
      setError("");
      try {
        const restauranteActual = await cargarRestaurante();
        if (restauranteActual.carrito_whatsapp_activo) {
          setTabActiva("whatsapp");
        } else if (restauranteActual.solicitudes_especiales_activas) {
          setTabActiva("especiales");
        }
        await cargarPedidos(restauranteActual);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar los pedidos.");
      } finally {
        setLoading(false);
      }
    };

    cargar();
  }, [cargarPedidos, cargarRestaurante]);

  const actualizarPedido = async (tipo, id, datos) => {
    setError("");
    setMensaje("");

    const endpoint =
      tipo === "whatsapp"
        ? `/mi-restaurante/pedidos/whatsapp/${id}/`
        : `/mi-restaurante/pedidos/especiales/${id}/`;

    try {
      const response = await authFetch(endpoint, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos),
      });

      if (!response.ok) {
        throw new Error(
          await obtenerMensajeError(response, "No se pudo actualizar el pedido.")
        );
      }

      const data = await response.json();
      const pedidoActualizado = data.pedido;

      if (tipo === "whatsapp") {
        setPedidosWhatsapp((actuales) =>
          actuales.map((pedido) =>
            pedido.id === id ? pedidoActualizado : pedido
          )
        );
      } else {
        setPedidosEspeciales((actuales) =>
          actuales.map((pedido) =>
            pedido.id === id ? pedidoActualizado : pedido
          )
        );
      }

      setMensaje("Pedido actualizado correctamente.");
      await cargarPedidos(restaurante);

      return true;
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el pedido.");
      return false;
    }
  };

  const abrirDetalle = (tipo, pedido) => {
    setDetalle({ tipo, pedido });
    setProductoBusqueda("");
    setProductoSeleccionado("");
    setCantidadProductoNuevo(1);
    setDireccionDetalle(pedido.direccion_entrega || "");
    setDetalleItems(
      tipo === "whatsapp"
        ? (pedido.productos_snapshot || []).map((item) => ({ ...item }))
        : []
    );
  };

  const totalDetalleWhatsapp = detalleItems.reduce((total, item) => (
    total + Number(item.cantidad || 0) * Number(item.precio_unitario || 0)
  ), 0);

  const cambiarCantidadDetalle = (index, cantidad) => {
    const cantidadNormalizada = Math.max(1, Number(cantidad) || 1);
    setDetalleItems((actuales) => actuales.map((item, itemIndex) => {
      if (itemIndex !== index) return item;
      return {
        ...item,
        cantidad: cantidadNormalizada,
        subtotal: cantidadNormalizada * Number(item.precio_unitario || 0),
      };
    }));
  };

  const eliminarItemDetalle = (index) => {
    setDetalleItems((actuales) => actuales.filter((_, itemIndex) => itemIndex !== index));
  };

  const productosFiltrados = useMemo(() => {
    const texto = productoBusqueda.trim().toLowerCase();
    if (!texto) return catalogoProductos.slice(0, 8);
    return catalogoProductos
      .filter((producto) => `${producto.nombre} ${producto.categoria?.nombre || ""}`.toLowerCase().includes(texto))
      .slice(0, 8);
  }, [catalogoProductos, productoBusqueda]);

  const agregarProductoDetalle = () => {
    const producto = catalogoProductos.find((item) => String(item.id) === String(productoSeleccionado));
    const cantidad = Math.max(1, Number(cantidadProductoNuevo) || 1);
    if (!producto) {
      setError("Selecciona un producto del catalogo.");
      return;
    }

    setError("");
    setDetalleItems((actuales) => {
      const existente = actuales.find((item) => Number(item.producto_id) === Number(producto.id));
      if (existente) {
        return actuales.map((item) => {
          if (Number(item.producto_id) !== Number(producto.id)) return item;
          const nuevaCantidad = Number(item.cantidad || 0) + cantidad;
          return {
            ...item,
            cantidad: nuevaCantidad,
            subtotal: nuevaCantidad * Number(item.precio_unitario || producto.precio || 0),
          };
        });
      }

      const precio = Number(producto.precio || 0);
      return [...actuales, {
        producto_id: producto.id,
        nombre: producto.nombre,
        precio_unitario: precio,
        cantidad,
        subtotal: precio * cantidad,
      }];
    });
    setProductoBusqueda("");
    setProductoSeleccionado("");
    setCantidadProductoNuevo(1);
  };

  const guardarProductosWhatsapp = async () => {
    if (!detalle || detalle.tipo !== "whatsapp") return;

    if (detalleItems.length === 0) {
      setError("El pedido debe tener al menos un producto.");
      return;
    }

    if (detalle.pedido.tipo_entrega === "delivery" && !direccionDetalle.trim()) {
      setError("Debe ingresar una direccion para delivery.");
      return;
    }

    const actualizado = await actualizarPedido("whatsapp", detalle.pedido.id, {
      direccion_entrega: direccionDetalle.trim(),
      productos: detalleItems.map((item) => ({
        producto_id: Number(item.producto_id),
        cantidad: Number(item.cantidad),
      })),
    });

    if (actualizado) {
      setDetalle(null);
    }
  };

  const abrirCrearEspecial = () => {
    setPedidoEditando(null);
    setFormEspecial(formEspecialInicial);
    setMostrarFormularioEspecial(true);
    setError("");
    setMensaje("");
  };

  const abrirEditarEspecial = (pedido) => {
    setPedidoEditando(pedido);
    setFormEspecial({
      nombre_cliente: pedido.nombre_cliente || "",
      telefono_cliente: pedido.telefono_cliente || "",
      email_cliente: pedido.email_cliente || "",
      descripcion_original: pedido.descripcion_original || "",
      fecha_entrega: pedido.fecha_entrega || "",
      estado: pedido.estado || "pendiente",
      items: pedido.items?.length ? pedido.items.map((item) => ({
        nombre: item.nombre || "",
        descripcion: item.descripcion || "",
        cantidad: item.cantidad || 1,
        precio_unitario: item.precio_unitario || 0,
      })) : formEspecialInicial.items,
    });
    setMostrarFormularioEspecial(true);
    setError("");
    setMensaje("");
  };

  const actualizarItemEspecial = (index, campo, valor) => {
    setFormEspecial((actual) => ({
      ...actual,
      items: actual.items.map((item, itemIndex) => (
        itemIndex === index ? { ...item, [campo]: valor } : item
      )),
    }));
  };

  const agregarItemEspecial = () => {
    setFormEspecial((actual) => ({
      ...actual,
      items: [...actual.items, { nombre: "", descripcion: "", cantidad: 1, precio_unitario: 0 }],
    }));
  };

  const quitarItemEspecial = (index) => {
    setFormEspecial((actual) => ({
      ...actual,
      items: actual.items.length === 1
        ? actual.items
        : actual.items.filter((_, itemIndex) => itemIndex !== index),
    }));
  };

  const guardarEspecial = async (e) => {
    e.preventDefault();
    setError("");
    setMensaje("");

    const itemsValidos = formEspecial.items.every((item) =>
      String(item.nombre || "").trim() &&
      Number(item.cantidad) > 0 &&
      Number(item.precio_unitario) >= 0
    );

    if (!itemsValidos || !formEspecial.fecha_entrega || !formEspecial.nombre_cliente || !formEspecial.telefono_cliente) {
      setError("Completa cliente, telefono, fecha de entrega e items del pedido.");
      return;
    }

    const payload = {
      ...formEspecial,
      items: formEspecial.items.map((item) => ({
        ...item,
        cantidad: Number(item.cantidad),
        precio_unitario: Number(item.precio_unitario),
      })),
    };

    try {
      const response = await authFetch(
        pedidoEditando
          ? `/mi-restaurante/pedidos/especiales/${pedidoEditando.id}/`
          : "/mi-restaurante/pedidos/especiales/",
        {
          method: pedidoEditando ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      if (!response.ok) {
        throw new Error(await obtenerMensajeError(response, "No se pudo guardar el pedido especial."));
      }

      setMostrarFormularioEspecial(false);
      setPedidoEditando(null);
      setFormEspecial(formEspecialInicial);
      setMensaje(pedidoEditando ? "Pedido especial actualizado." : "Pedido especial creado.");
      await cargarPedidos(restaurante);
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el pedido especial.");
    }
  };

  const totalFormEspecial = formEspecial.items.reduce((total, item) => (
    total + Number(item.cantidad || 0) * Number(item.precio_unitario || 0)
  ), 0);

  if (loading) {
    return <p className="reservas-loading">Cargando pedidos...</p>;
  }

  return (
    <div className="body">
      <main className="container-fluid" id="main">
        <MainMenu />

        <section className="reservas-page pedidos-page">
          <header className="reservas-header">
            <h1>Pedidos</h1>
            {error && <p className="reservas-error">{error}</p>}
            {mensaje && <p className="solicitudes-success">{mensaje}</p>}

            <div className="breadcrumb-reservas">
              <span>Inicio</span>
              <span>›</span>
              <strong>Pedidos</strong>
            </div>
          </header>

          {tabsDisponibles.length === 0 ? (
            <section className="reservas-table-card">
              <p className="empty-state">El modulo de pedidos no esta activo para este restaurante.</p>
            </section>
          ) : (
            <>
              <section className="reservas-stats pedidos-stats">
                {whatsappActivo && (
                  <>
                    <div className="reserva-stat-card">
                      <div className="stat-icon"><i className="bi bi-currency-dollar"></i></div>
                      <div>
                        <h3>{formatearMoneda(metricas.whatsapp?.venta_diaria_total)}</h3>
                        <p>Venta diaria WhatsApp</p>
                      </div>
                    </div>
                    <div className="reserva-stat-card">
                      <div className="stat-icon"><i className="bi bi-bag-check"></i></div>
                      <div>
                        <h3>{metricas.whatsapp?.pedidos_diarios || 0}</h3>
                        <p>Pedidos WhatsApp hoy</p>
                      </div>
                    </div>
                    <div className="reserva-stat-card">
                      <div className="stat-icon"><i className="bi bi-star"></i></div>
                      <div>
                        <h3>{metricas.whatsapp?.producto_mas_vendido_dia?.cantidad || 0}</h3>
                        <p>{metricas.whatsapp?.producto_mas_vendido_dia?.nombre || "Producto mas vendido"}</p>
                      </div>
                    </div>
                  </>
                )}

                {especialesActivo && (
                  <div className="reserva-stat-card">
                    <div className="stat-icon"><i className="bi bi-calendar-heart"></i></div>
                    <div>
                      <h3>{metricas.especiales?.pedidos_pendientes || 0}</h3>
                      <p>Pedidos especiales pendientes</p>
                    </div>
                  </div>
                )}

                <div className="reserva-stat-card">
                  <div className="stat-icon"><i className="bi bi-x-circle"></i></div>
                  <div>
                    <h3>{(metricas.whatsapp?.pedidos_cancelados || 0) + (metricas.especiales?.pedidos_cancelados || 0)}</h3>
                    <p>Cancelados</p>
                  </div>
                </div>
              </section>

              <section className="reservas-tools">
                <div className="tabs-row pedidos-tabs">
                  {whatsappActivo && (
                    <button className={`tab ${tabActiva === "whatsapp" ? "active" : ""}`} onClick={() => setTabActiva("whatsapp")}>
                      Pedidos por WhatsApp ({pedidosWhatsapp.length})
                    </button>
                  )}
                  {especialesActivo && (
                    <button className={`tab ${tabActiva === "especiales" ? "active" : ""}`} onClick={() => setTabActiva("especiales")}>
                      Pedidos especiales ({pedidosEspeciales.length})
                    </button>
                  )}
                  {especialesActivo && (
                    <button className="crear-reserva-btn" type="button" onClick={abrirCrearEspecial}>
                      <i className="bi bi-plus-lg"></i>
                      Nuevo pedido especial
                    </button>
                  )}
                </div>
              </section>

              {tabActiva === "whatsapp" && (
                <section className="reservas-table-card">
                  <table className="reservas-table pedidos-table">
                    <thead>
                      <tr>
                        <th>N°</th>
                        <th>Cliente</th>
                        <th>Entrega</th>
                        <th>Productos</th>
                        <th>Total</th>
                        <th>Estado</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pedidosWhatsapp.length === 0 ? (
                        <tr><td colSpan="7" className="empty-state">No hay pedidos por WhatsApp.</td></tr>
                      ) : pedidosWhatsapp.map((pedido) => (
                        <tr key={pedido.id}>
                          <td>#{pedido.numero_pedido}</td>
                          <td>
                            <strong>{pedido.nombre_cliente}</strong>
                            <small>{pedido.telefono_cliente}</small>
                          </td>
                          <td>
                            {pedido.tipo_entrega_display || pedido.tipo_entrega}
                            {pedido.direccion_entrega && <small>{pedido.direccion_entrega}</small>}
                          </td>
                          <td>{resumenItems(pedido.productos_snapshot)}</td>
                          <td>{formatearMoneda(pedido.total)}</td>
                          <td><span className={`estado-badge ${pedido.estado}`}>{estadoLabels[pedido.estado] || pedido.estado}</span></td>
                          <td>
                            <div className="acciones-cell">
                              <button title="Ver detalle" onClick={() => abrirDetalle("whatsapp", pedido)}>
                                <i className="bi bi-eye"></i>
                              </button>
                              <select className="pedido-estado-select" value={pedido.estado} onChange={(e) => actualizarPedido("whatsapp", pedido.id, { estado: e.target.value })}>
                                {ESTADOS_PEDIDO.concat("completado").map((estado) => (
                                  <option key={estado} value={estado}>{estadoLabels[estado]}</option>
                                ))}
                              </select>
                              <button className="delete" title="Cancelar" onClick={() => actualizarPedido("whatsapp", pedido.id, { estado: "cancelado" })}>
                                <i className="bi bi-x-lg"></i>
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              )}

              {tabActiva === "especiales" && (
                <section className="reservas-table-card">
                  <table className="reservas-table pedidos-table">
                    <thead>
                      <tr>
                        <th>N°</th>
                        <th>Cliente</th>
                        <th>Entrega</th>
                        <th>Items</th>
                        <th>Total</th>
                        <th>Estado</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pedidosEspeciales.length === 0 ? (
                        <tr><td colSpan="7" className="empty-state">No hay pedidos especiales.</td></tr>
                      ) : pedidosEspeciales.map((pedido) => (
                        <tr key={pedido.id}>
                          <td>#{pedido.numero_pedido}</td>
                          <td>
                            <strong>{pedido.nombre_cliente}</strong>
                            <small>{pedido.telefono_cliente}</small>
                          </td>
                          <td>{formatearFecha(`${pedido.fecha_entrega}T00:00:00`)}</td>
                          <td>{resumenItems(pedido.items)}</td>
                          <td>{formatearMoneda(pedido.total)}</td>
                          <td><span className={`estado-badge ${pedido.estado}`}>{estadoLabels[pedido.estado] || pedido.estado}</span></td>
                          <td>
                            <div className="acciones-cell">
                              <button title="Ver detalle" onClick={() => abrirDetalle("especial", pedido)}>
                                <i className="bi bi-eye"></i>
                              </button>
                              <button title="Editar" onClick={() => abrirEditarEspecial(pedido)}>
                                <i className="bi bi-pencil-square"></i>
                              </button>
                              <select className="pedido-estado-select" value={pedido.estado} onChange={(e) => actualizarPedido("especial", pedido.id, { estado: e.target.value })}>
                                {ESTADOS_PEDIDO.map((estado) => (
                                  <option key={estado} value={estado}>{estadoLabels[estado]}</option>
                                ))}
                              </select>
                              <button className="delete" title="Cancelar" onClick={() => actualizarPedido("especial", pedido.id, { estado: "cancelado" })}>
                                <i className="bi bi-x-lg"></i>
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              )}
            </>
          )}
        </section>

        {detalle && (
          <div className="modal-reserva-bg">
            <section className="modal-reserva pedido-detalle-modal">
              <button className="modal-close-btn" type="button" aria-label="Cerrar" onClick={() => setDetalle(null)}>
                <i className="bi bi-x-lg"></i>
              </button>

              <div className="pedido-modal-header">
                <div>
                  <h2>Pedido #{detalle.pedido.numero_pedido}</h2>
                  <p className="pedido-detalle-subtitle">
                    {detalle.tipo === "whatsapp" ? "Pedido por WhatsApp" : "Pedido especial"}
                  </p>
                </div>
                <span className={`estado-badge ${detalle.pedido.estado}`}>
                  {estadoLabels[detalle.pedido.estado] || detalle.pedido.estado}
                </span>
              </div>

              <div className="pedido-detalle-layout">
                <section className="pedido-modal-panel">
                  <h3>Informacion del pedido</h3>
                  <dl className="pedido-info-list">
                    <div><dt>Numero</dt><dd>#{detalle.pedido.numero_pedido}</dd></div>
                    <div><dt>Cliente</dt><dd>{detalle.pedido.nombre_cliente}</dd></div>
                    <div><dt>Telefono</dt><dd>{detalle.pedido.telefono_cliente}</dd></div>
                    {detalle.pedido.tipo_entrega_display && (
                      <div><dt>Tipo de entrega</dt><dd>{detalle.pedido.tipo_entrega_display}</dd></div>
                    )}
                    {detalle.pedido.direccion_entrega && (
                      <div><dt>Direccion</dt><dd>{detalle.pedido.direccion_entrega}</dd></div>
                    )}
                    <div><dt>Estado</dt><dd>{estadoLabels[detalle.pedido.estado] || detalle.pedido.estado}</dd></div>
                    <div>
                      <dt>Fecha</dt>
                      <dd>
                        {detalle.pedido.fecha_entrega
                          ? formatearFecha(`${detalle.pedido.fecha_entrega}T00:00:00`)
                          : formatearFecha(detalle.pedido.fecha_creacion)}
                      </dd>
                    </div>
                    <div><dt>Total</dt><dd>{formatearMoneda(detalle.tipo === "whatsapp" ? totalDetalleWhatsapp : detalle.pedido.total)}</dd></div>
                  </dl>

                  {detalle.pedido.descripcion_original && (
                    <p className="pedido-descripcion">{detalle.pedido.descripcion_original}</p>
                  )}

                  {detalle.tipo === "whatsapp" && detalle.pedido.tipo_entrega === "delivery" && (
                    <label className="pedido-direccion-field">
                      Direccion de entrega
                      <textarea
                        value={direccionDetalle}
                        onChange={(e) => setDireccionDetalle(e.target.value)}
                        placeholder="Direccion de entrega"
                      />
                    </label>
                  )}
                </section>

                <section className="pedido-modal-panel">
                  <h3>Productos</h3>

                  {detalle.tipo === "whatsapp" ? (
                    <>
                      <div className="pedido-productos-editables">
                        {detalleItems.map((item, index) => (
                          <div className="pedido-producto-row" key={`${item.producto_id}-${index}`}>
                            <div>
                              <strong>{item.nombre}</strong>
                              <small>{formatearMoneda(item.precio_unitario)} c/u</small>
                            </div>
                            <div className="pedido-cantidad-control">
                              <button type="button" onClick={() => cambiarCantidadDetalle(index, Number(item.cantidad) - 1)}>
                                <i className="bi bi-dash"></i>
                              </button>
                              <input
                                type="number"
                                min="1"
                                value={item.cantidad}
                                onChange={(e) => cambiarCantidadDetalle(index, e.target.value)}
                              />
                              <button type="button" onClick={() => cambiarCantidadDetalle(index, Number(item.cantidad) + 1)}>
                                <i className="bi bi-plus"></i>
                              </button>
                            </div>
                            <strong>{formatearMoneda(item.subtotal)}</strong>
                            <button className="pedido-icon-danger" type="button" onClick={() => eliminarItemDetalle(index)}>
                              <i className="bi bi-trash"></i>
                            </button>
                          </div>
                        ))}
                      </div>

                      <div className="pedido-agregar-producto">
                        <label>Agregar desde catalogo</label>
                        <input
                          type="search"
                          placeholder="Buscar producto..."
                          value={productoBusqueda}
                          onChange={(e) => setProductoBusqueda(e.target.value)}
                        />
                        <select
                          value={productoSeleccionado}
                          onChange={(e) => setProductoSeleccionado(e.target.value)}
                        >
                          <option value="">Seleccionar producto</option>
                          {productosFiltrados.map((producto) => (
                            <option key={producto.id} value={producto.id}>
                              {producto.nombre} - {formatearMoneda(producto.precio)}
                            </option>
                          ))}
                        </select>
                        <input
                          type="number"
                          min="1"
                          value={cantidadProductoNuevo}
                          onChange={(e) => setCantidadProductoNuevo(e.target.value)}
                        />
                        <button type="button" onClick={agregarProductoDetalle}>
                          Agregar
                        </button>
                      </div>

                      <div className="pedido-total-line">
                        <span>Total</span>
                        <strong>{formatearMoneda(totalDetalleWhatsapp)}</strong>
                      </div>

                      <div className="modal-actions">
                        <button className="button-cancelar" type="button" onClick={() => setDetalle(null)}>
                          Cancelar
                        </button>
                        <button type="button" onClick={guardarProductosWhatsapp}>
                          Guardar cambios
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="pedido-items-detalle">
                        {(detalle.pedido.items || []).map((item, index) => (
                          <div key={`${item.nombre}-${index}`}>
                            <span>{item.cantidad} x {item.nombre}</span>
                            <small>{formatearMoneda(item.precio_unitario)} c/u</small>
                            <strong>{formatearMoneda(item.subtotal)}</strong>
                          </div>
                        ))}
                      </div>
                      <div className="pedido-total-line">
                        <span>Total</span>
                        <strong>{formatearMoneda(detalle.pedido.total)}</strong>
                      </div>
                    </>
                  )}
                </section>
              </div>
            </section>
          </div>
        )}

        {mostrarFormularioEspecial && (
          <div className="modal-reserva-bg">
            <form className="modal-reserva pedido-form-modal" onSubmit={guardarEspecial}>
              <button className="modal-close-btn" type="button" aria-label="Cerrar" onClick={() => setMostrarFormularioEspecial(false)}>
                <i className="bi bi-x-lg"></i>
              </button>

              <div className="pedido-modal-header">
                <div>
                  <h2>{pedidoEditando ? "Editar pedido especial" : "Nuevo pedido especial"}</h2>
                  <p className="pedido-detalle-subtitle">Datos del cliente e items acordados</p>
                </div>
              </div>

              <section className="pedido-form-section">
                <h3>Cliente</h3>
                <div className="pedido-form-grid">
                  <label>
                    Nombre cliente
                    <input
                      type="text"
                      value={formEspecial.nombre_cliente}
                      onChange={(e) => setFormEspecial({ ...formEspecial, nombre_cliente: e.target.value })}
                      required
                    />
                  </label>
                  <label>
                    Telefono
                    <input
                      type="text"
                      value={formEspecial.telefono_cliente}
                      onChange={(e) => setFormEspecial({ ...formEspecial, telefono_cliente: e.target.value })}
                      required
                    />
                  </label>
                  <label>
                    Email opcional
                    <input
                      type="email"
                      value={formEspecial.email_cliente}
                      onChange={(e) => setFormEspecial({ ...formEspecial, email_cliente: e.target.value })}
                    />
                  </label>
                  <label>
                    Fecha entrega
                    <input
                      type="date"
                      value={formEspecial.fecha_entrega}
                      onChange={(e) => setFormEspecial({ ...formEspecial, fecha_entrega: e.target.value })}
                      required
                    />
                  </label>
                </div>
                <label>
                  Descripcion o notas
                  <textarea
                    value={formEspecial.descripcion_original}
                    onChange={(e) => setFormEspecial({ ...formEspecial, descripcion_original: e.target.value })}
                  />
                </label>
              </section>

              <section className="pedido-form-section">
                <div className="pedido-section-heading">
                  <h3>Items</h3>
                  <button type="button" className="export-btn" onClick={agregarItemEspecial}>
                    <i className="bi bi-plus-lg"></i>
                    Agregar item
                  </button>
                </div>

                <div className="pedido-items-form">
                  {formEspecial.items.map((item, index) => (
                    <div className="pedido-item-row pedido-item-row-wide" key={index}>
                      <label>
                        Item
                        <input
                          type="text"
                          value={item.nombre}
                          onChange={(e) => actualizarItemEspecial(index, "nombre", e.target.value)}
                          required
                        />
                      </label>
                      <label>
                        Cantidad
                        <input
                          type="number"
                          min="1"
                          value={item.cantidad}
                          onChange={(e) => actualizarItemEspecial(index, "cantidad", e.target.value)}
                          required
                        />
                      </label>
                      <label>
                        Precio unitario
                        <input
                          type="number"
                          min="0"
                          value={item.precio_unitario}
                          onChange={(e) => actualizarItemEspecial(index, "precio_unitario", e.target.value)}
                          required
                        />
                      </label>
                      <div className="pedido-subtotal-cell">
                        <span>Subtotal</span>
                        <strong>{formatearMoneda(Number(item.cantidad || 0) * Number(item.precio_unitario || 0))}</strong>
                      </div>
                      <button type="button" className="pedido-icon-danger" onClick={() => quitarItemEspecial(index)}>
                        <i className="bi bi-trash"></i>
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              <div className="pedido-total-line pedido-form-total-line">
                <span>Total</span>
                <strong>{formatearMoneda(totalFormEspecial)}</strong>
              </div>

              <div className="modal-actions">
                <button className="button-cancelar" type="button" onClick={() => setMostrarFormularioEspecial(false)}>
                  Cancelar
                </button>
                <button type="submit">Guardar pedido</button>
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
