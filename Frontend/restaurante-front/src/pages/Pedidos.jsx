import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "../styles/ReservasDashboard.css";
import MainMenu from "../componentes/Main-menu";
import ConfirmarCancelacionPedido from "../componentes/ConfirmarCancelacionPedido";
import { useSearchParams } from "react-router-dom";
import { authFetch, readJsonResponse } from "../api";
import { permisosPorRol } from "../utils/permisos";
import {
  PAGINACION_INICIAL,
  normalizarListaPedidos,
  normalizarPaginacionPedidos,
} from "../utils/paginacionPedidos";
import nuevoPedidoSound from "../assets/sound/Nuevo-Pedido.mp3";
import {
  ESTADO_CANCELADO,
  estadoLabels,
  normalizarTipoPedido,
  obtenerEndpointActualizacionPedido,
  obtenerEndpointDetallePedido,
  obtenerEstadosPedido,
} from "../utils/pedidos";
const PEDIDOS_POLLING_MS = 10000;

const formEspecialInicial = {
  nombre_cliente: "",
  telefono_cliente: "",
  email_cliente: "",
  descripcion_original: "",
  fecha_entrega: "",
  estado: "pendiente",
  items: [{ nombre: "", descripcion: "", cantidad: 1, precio_unitario: 0 }],
};

const formManualInicial = {
  nombre_cliente: "",
  telefono_cliente: "",
  tipo_entrega: "mesa",
  direccion: "",
  numero_mesa: "",
  observaciones: "",
  items: [],
};

const obtenerVariantesActivas = (producto) => (
  Array.isArray(producto?.variantes)
    ? producto.variantes.filter((variante) => variante.activo !== false)
    : []
);

const claveLineaManual = (item, varianteId = null) => {
  const productoId = typeof item === "object" ? item.producto_id : item;
  const variante = typeof item === "object" ? item.variante_id : varianteId;
  return `${productoId}:${variante || "base"}`;
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

const resumenItems = (items = [], etiquetaSingular = "producto", etiquetaPlural = "productos") => {
  const totalItems = items.reduce(
    (total, item) => total + Number(item?.cantidad || 0),
    0
  );
  const etiqueta = totalItems === 1 ? etiquetaSingular : etiquetaPlural;

  return (
    <span className="pedido-productos-resumen">
      <strong>{totalItems} {etiqueta}</strong>
      <small>Ver detalle</small>
    </span>
  );
};

const normalizarTelefonoWhatsappChile = (telefono) => {
  const soloDigitos = String(telefono || "").replace(/\D/g, "");
  if (/^9\d{8}$/.test(soloDigitos)) return `56${soloDigitos}`;
  if (/^56\d{9}$/.test(soloDigitos)) return soloDigitos;
  return "";
};

const obtenerNombreItemPedido = (item) => {
  const nombre = item?.nombre_producto || item?.nombre || "Producto";
  return item?.variante_nombre ? `${nombre} — ${item.variante_nombre}` : nombre;
};

const construirMensajeWhatsappPedidoManual = (pedido, restaurante) => {
  const nombreCliente = (pedido?.nombre_cliente || pedido?.cliente_nombre || "").trim();
  const saludo = nombreCliente ? `Hola ${nombreCliente}` : "Hola";
  const restauranteNombre = restaurante?.nombre_empresa || restaurante?.nombre || "Menly";
  const items = pedido?.items?.length
    ? pedido.items.map((item) => `- ${item.cantidad} x ${obtenerNombreItemPedido(item)}`).join("\n")
    : "- Pedido registrado";

  return [
    saludo,
    "",
    `Tu pedido #${pedido.numero_pedido} fue registrado correctamente en ${restauranteNombre}.`,
    "",
    "Detalle del pedido:",
    items,
    "",
    `Total: ${formatearMoneda(pedido.total)}`,
    `Tipo de entrega: ${pedido.tipo_entrega_display || pedido.tipo_entrega || "No informado"}`,
    "",
    "Puedes revisar el estado actualizado de tu pedido aqui:",
    pedido.tracking_url || "",
    "",
    "Gracias por tu compra.",
  ].join("\n");
};

function PaginacionPedidos({ paginacion, onAnterior, onSiguiente }) {
  return (
    <footer className="section-paginations-info">
      <span className="div-info-paginacion">
        Página {paginacion.page} de {paginacion.totalPages} · {paginacion.count} pedidos
      </span>
      <div className="paginations">
        <button type="button" disabled={!paginacion.previous} onClick={onAnterior}>
          Anterior
        </button>
        <button type="button" disabled={!paginacion.next} onClick={onSiguiente}>
          Siguiente
        </button>
      </div>
    </footer>
  );
}

export default function PedidosDashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [restaurante, setRestaurante] = useState(null);
  const [usuario, setUsuario] = useState(null);
  const [catalogoProductos, setCatalogoProductos] = useState([]);
  const [tabActiva, setTabActiva] = useState("");
  const [pedidosWhatsapp, setPedidosWhatsapp] = useState([]);
  const [pedidosEspeciales, setPedidosEspeciales] = useState([]);
  const [pedidosManuales, setPedidosManuales] = useState([]);
  const [paginacionPedidos, setPaginacionPedidos] = useState({
    menly: PAGINACION_INICIAL,
    whatsapp: PAGINACION_INICIAL,
    especiales: PAGINACION_INICIAL,
  });
  const [metricas, setMetricas] = useState({ whatsapp: {}, especiales: {} });
  const [loading, setLoading] = useState(true);
  const [detalle, setDetalle] = useState(null);
  const [mostrarFormularioEspecial, setMostrarFormularioEspecial] = useState(false);
  const [mostrarFormularioManual, setMostrarFormularioManual] = useState(false);
  const [pedidoEditando, setPedidoEditando] = useState(null);
  const [pedidoManualEditando, setPedidoManualEditando] = useState(null);
  const [formEspecial, setFormEspecial] = useState(formEspecialInicial);
  const [formManual, setFormManual] = useState(formManualInicial);
  const [guardandoManual, setGuardandoManual] = useState(false);
  const [abriendoCocina, setAbriendoCocina] = useState(false);
  const [cancelacionPendiente, setCancelacionPendiente] = useState(null);
  const [confirmandoCancelacion, setConfirmandoCancelacion] = useState(false);
  const [cancelacionError, setCancelacionError] = useState("");
  const [estadoError, setEstadoError] = useState("");
  const [observacionManualEditor, setObservacionManualEditor] = useState(null);
  const [varianteManualSelector, setVarianteManualSelector] = useState(null);
  const [detalleItems, setDetalleItems] = useState([]);
  const [productoBusqueda, setProductoBusqueda] = useState("");
  const [productoBusquedaManual, setProductoBusquedaManual] = useState("");
  const [categoriaManual, setCategoriaManual] = useState("");
  const [productoSeleccionado, setProductoSeleccionado] = useState("");
  const [cantidadProductoNuevo, setCantidadProductoNuevo] = useState(1);
  const [direccionDetalle, setDireccionDetalle] = useState("");
  const detalleAbiertoRef = useRef(false);
  const formularioEspecialAbiertoRef = useRef(false);
  const formularioManualAbiertoRef = useRef(false);
  const observacionManualButtonsRef = useRef({});
  const estadoErrorTimerRef = useRef(null);
  const ultimoErrorEstadoRef = useRef("");
  const cargaInicialPromiseRef = useRef(null);
  const pedidosWhatsappConocidosRef = useRef(null);
  const nuevoPedidoAudioRef = useRef(null);
  const paginaOcultaRef = useRef(document.hidden);
  const paginasPedidosRef = useRef({ menly: 1, whatsapp: 1, especiales: 1 });
  const pedidoQueryTipo = normalizarTipoPedido(searchParams.get("tipo"));
  const pedidoQueryId = searchParams.get("pedido");

  const whatsappActivo = restaurante?.carrito_whatsapp_activo === true;
  const especialesActivo = restaurante?.solicitudes_especiales_activas === true;
  const posActivo = restaurante?.pedidos_pos === true;
  const deliveryActivo = restaurante?.delivery_activo === true;
  const esEmpleado = permisosPorRol(usuario?.rol).isEmpleado;
  const puedeAbrirCocina = ["dueno", "admin"].includes(usuario?.rol);
  const obtenerEstadosPedidoWhatsapp = (pedido) =>
    obtenerEstadosPedido("whatsapp", pedido, { deliveryActivo });
  const obtenerEstadosPedidoPanel = (tipo, pedido) =>
    obtenerEstadosPedido(tipo, pedido, { deliveryActivo });

  const mostrarErrorEstado = (mensaje) => {
    ultimoErrorEstadoRef.current = mensaje;
    setEstadoError(mensaje);
    window.clearTimeout(estadoErrorTimerRef.current);
    estadoErrorTimerRef.current = window.setTimeout(() => setEstadoError(""), 5000);
  };

  const tabsDisponibles = useMemo(() => {
    const tabs = [];
    if (posActivo) tabs.push("menly");
    if (whatsappActivo) tabs.push("whatsapp");
    if (especialesActivo) tabs.push("especiales");
    return tabs;
  }, [posActivo, whatsappActivo, especialesActivo]);
  const mainMenuData = useMemo(
    () => (restaurante ? { restaurante, usuario } : null),
    [restaurante, usuario]
  );

  const cargarRestaurante = useCallback(async () => {
    const response = await authFetch("/mi-restaurante/", { cache: "no-store" });
    const data = await readJsonResponse(
      response,
      "/mi-restaurante/",
      "No se pudo cargar el restaurante."
    );
    setRestaurante(data.restaurante);
    setUsuario(data.usuario || null);
    setCatalogoProductos((data.productos || []).filter((producto) => producto.disponible !== false));
    return data;
  }, []);

  const cargarMetricas = useCallback(async (rolActual) => {
    if (permisosPorRol(rolActual).isEmpleado) {
      setMetricas({ whatsapp: {}, especiales: {} });
      return;
    }

    const response = await authFetch("/mi-restaurante/pedidos/metricas/");
    const data = await readJsonResponse(
      response,
      "/mi-restaurante/pedidos/metricas/",
      "No se pudieron cargar las metricas."
    );
    setMetricas(data);
  }, []);

  const cargarListasPedidos = useCallback(async (restauranteActual, paginas = paginasPedidosRef.current) => {
    if (!restauranteActual) return;

    const paginasSolicitadas = { ...paginas };
    const solicitudes = [];

    if (restauranteActual.carrito_whatsapp_activo === true) {
      solicitudes.push({
        tipo: "whatsapp",
        endpoint: `/mi-restaurante/pedidos/whatsapp/?page=${paginasSolicitadas.whatsapp}&scope=turno_actual`,
      });
      if (paginasSolicitadas.whatsapp !== 1) {
        solicitudes.push({
          tipo: "whatsappRecientes",
          endpoint: "/mi-restaurante/pedidos/whatsapp/?page=1&scope=turno_actual",
        });
      }
    }

    if (restauranteActual.solicitudes_especiales_activas === true) {
      solicitudes.push({
        tipo: "especiales",
        endpoint: `/mi-restaurante/pedidos/especiales/?page=${paginasSolicitadas.especiales}&scope=turno_actual`,
      });
    }

    if (restauranteActual.pedidos_pos === true) {
      solicitudes.push({
        tipo: "menly",
        endpoint: `/mi-restaurante/pedidos/manuales/?page=${paginasSolicitadas.menly}&scope=turno_actual`,
      });
    }

    const respuestas = await Promise.all(
      solicitudes.map(async ({ tipo, endpoint }) => ({
        tipo,
        endpoint,
        response: await authFetch(endpoint),
      }))
    );

    const paginaPorTipo = {
      whatsapp: paginasSolicitadas.whatsapp,
      especiales: paginasSolicitadas.especiales,
      menly: paginasSolicitadas.menly,
    };
    for (const solicitud of respuestas) {
      const pagina = paginaPorTipo[solicitud.tipo];
      if (solicitud.response.status !== 404 || !pagina || pagina === 1) continue;

      solicitud.endpoint = solicitud.endpoint.replace(/page=\d+/, "page=1");
      solicitud.response = await authFetch(solicitud.endpoint);
      paginasSolicitadas[solicitud.tipo] = 1;
      paginasPedidosRef.current = {
        ...paginasPedidosRef.current,
        [solicitud.tipo]: 1,
      };
    }
    const respuestasPorTipo = new Map(respuestas.map((item) => [item.tipo, item]));

    if (restauranteActual.carrito_whatsapp_activo === true) {
      const solicitudWhatsapp = respuestasPorTipo.get("whatsapp");
      const data = await readJsonResponse(
        solicitudWhatsapp.response,
        solicitudWhatsapp.endpoint,
        "No se pudieron cargar los pedidos WhatsApp."
      );
      const listaPedidosWhatsapp = normalizarListaPedidos(data);
      const solicitudRecientes = respuestasPorTipo.get("whatsappRecientes");
      const dataRecientes = solicitudRecientes
        ? await readJsonResponse(
            solicitudRecientes.response,
            solicitudRecientes.endpoint,
            "No se pudieron comprobar los pedidos WhatsApp recientes."
          )
        : data;
      const idsActuales = normalizarListaPedidos(dataRecientes).map((pedido) => String(pedido.id));
      const storageKey = `menly:pedidos-whatsapp-conocidos:${restauranteActual.id}`;

      if (pedidosWhatsappConocidosRef.current === null) {
        let idsPersistidos = [];
        try {
          const valorPersistido = JSON.parse(window.localStorage.getItem(storageKey) || "[]");
          idsPersistidos = Array.isArray(valorPersistido) ? valorPersistido : [];
        } catch {
          idsPersistidos = [];
        }
        pedidosWhatsappConocidosRef.current = new Set([...idsPersistidos, ...idsActuales]);
      } else {
        const idsNuevos = idsActuales.filter(
          (pedidoId) => !pedidosWhatsappConocidosRef.current.has(pedidoId)
        );
        idsActuales.forEach((pedidoId) => pedidosWhatsappConocidosRef.current.add(pedidoId));

        if (idsNuevos.length > 0 && !paginaOcultaRef.current) {
          if (!nuevoPedidoAudioRef.current) {
            nuevoPedidoAudioRef.current = new Audio(nuevoPedidoSound);
          }
          nuevoPedidoAudioRef.current.currentTime = 0;
          nuevoPedidoAudioRef.current.play().catch(() => {});
        }
      }

      try {
        window.localStorage.setItem(
          storageKey,
          JSON.stringify(Array.from(pedidosWhatsappConocidosRef.current))
        );
      } catch {
        // La deteccion en memoria sigue activa si el almacenamiento no esta disponible.
      }

      setPedidosWhatsapp(listaPedidosWhatsapp);
      setPaginacionPedidos((actual) => ({
        ...actual,
        whatsapp: normalizarPaginacionPedidos(data, paginasSolicitadas.whatsapp),
      }));
    } else {
      setPedidosWhatsapp([]);
      setPaginacionPedidos((actual) => ({ ...actual, whatsapp: PAGINACION_INICIAL }));
    }

    if (restauranteActual.solicitudes_especiales_activas === true) {
      const solicitudEspeciales = respuestasPorTipo.get("especiales");
      const data = await readJsonResponse(
        solicitudEspeciales.response,
        solicitudEspeciales.endpoint,
        "No se pudieron cargar los pedidos especiales."
      );
      setPedidosEspeciales(normalizarListaPedidos(data));
      setPaginacionPedidos((actual) => ({
        ...actual,
        especiales: normalizarPaginacionPedidos(data, paginasSolicitadas.especiales),
      }));
    } else {
      setPedidosEspeciales([]);
      setPaginacionPedidos((actual) => ({ ...actual, especiales: PAGINACION_INICIAL }));
    }

    if (restauranteActual.pedidos_pos === true) {
      const solicitudMenly = respuestasPorTipo.get("menly");
      const manualesData = await readJsonResponse(
        solicitudMenly.response,
        solicitudMenly.endpoint,
        "No se pudieron cargar los pedidos Menly."
      );
      setPedidosManuales(normalizarListaPedidos(manualesData));
      setPaginacionPedidos((actual) => ({
        ...actual,
        menly: normalizarPaginacionPedidos(manualesData, paginasSolicitadas.menly),
      }));
    } else {
      setPedidosManuales([]);
      setPaginacionPedidos((actual) => ({ ...actual, menly: PAGINACION_INICIAL }));
    }
  }, []);

  const cambiarPaginaPedidos = useCallback(async (tipo, pagina) => {
    const paginas = {
      ...paginasPedidosRef.current,
      [tipo]: Math.max(1, pagina),
    };
    paginasPedidosRef.current = paginas;
    await cargarListasPedidos(restaurante, paginas);
  }, [cargarListasPedidos, restaurante]);

  const cargarPedidos = useCallback(
    async (restauranteActual, rolActual) => {
      if (!restauranteActual) return;
      await Promise.all([
        cargarMetricas(rolActual),
        cargarListasPedidos(restauranteActual),
      ]);
    },
    [cargarListasPedidos, cargarMetricas]
  );

  useEffect(() => {
    if (cargaInicialPromiseRef.current) return undefined;

    const cargar = async () => {
      setLoading(true);
      try {
        const datosRestaurante = await cargarRestaurante();
        const restauranteActual = datosRestaurante.restaurante;
        if (restauranteActual.pedidos_pos) {
          setTabActiva("menly");
        } else if (restauranteActual.carrito_whatsapp_activo) {
          setTabActiva("whatsapp");
        } else if (restauranteActual.solicitudes_especiales_activas) {
          setTabActiva("especiales");
        }
        await cargarPedidos(restauranteActual, datosRestaurante.usuario?.rol);
      } catch {
        // La pantalla conserva su estado sin insertar alertas sobre las métricas.
      } finally {
        setLoading(false);
      }
    };

    cargaInicialPromiseRef.current = cargar();
    return undefined;
  }, [cargarPedidos, cargarRestaurante]);

  useEffect(() => {
    const actualizarVisibilidad = () => {
      paginaOcultaRef.current = document.hidden;
    };

    document.addEventListener("visibilitychange", actualizarVisibilidad);
    return () => document.removeEventListener("visibilitychange", actualizarVisibilidad);
  }, []);

  useEffect(() => {
    const registrarPedidoNotificadoPorPush = (event) => {
      if (event.data?.type !== "MENLY_PUSH_NOTIFICADO" || !event.data.pedido_id) return;

      const pedidoId = String(event.data.pedido_id);
      pedidosWhatsappConocidosRef.current?.add(pedidoId);
      if (!restaurante?.id || !pedidosWhatsappConocidosRef.current) return;

      try {
        window.localStorage.setItem(
          `menly:pedidos-whatsapp-conocidos:${restaurante.id}`,
          JSON.stringify(Array.from(pedidosWhatsappConocidosRef.current))
        );
      } catch {
        // La marca en memoria evita duplicar el sonido durante esta carga.
      }
    };

    navigator.serviceWorker?.addEventListener("message", registrarPedidoNotificadoPorPush);
    return () => navigator.serviceWorker?.removeEventListener("message", registrarPedidoNotificadoPorPush);
  }, [restaurante?.id]);

  useEffect(() => {
    detalleAbiertoRef.current = Boolean(detalle);
  }, [detalle]);

  useEffect(() => {
    formularioEspecialAbiertoRef.current = mostrarFormularioEspecial;
  }, [mostrarFormularioEspecial]);

  useEffect(() => {
    formularioManualAbiertoRef.current = mostrarFormularioManual;
  }, [mostrarFormularioManual]);

  useEffect(() => {
    if (!restaurante) return undefined;

    const intervalId = window.setInterval(() => {
      if (detalleAbiertoRef.current || formularioEspecialAbiertoRef.current || formularioManualAbiertoRef.current) return;

      cargarPedidos(restaurante, usuario?.rol).catch(() => {
        // El polling es silencioso: conserva la vista actual si un refresco falla.
      });
    }, PEDIDOS_POLLING_MS);

    return () => window.clearInterval(intervalId);
  }, [cargarPedidos, restaurante, usuario?.rol]);

  const actualizarPedido = async (tipo, id, datos) => {

    const endpoint = obtenerEndpointActualizacionPedido(tipo, id, datos);

    try {
      const response = await authFetch(endpoint, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos),
      });

      const data = await readJsonResponse(
        response,
        endpoint,
        "No se pudo actualizar el pedido."
      );
      const pedidoActualizado = data.pedido;

      if (tipo === "whatsapp") {
        setPedidosWhatsapp((actuales) =>
          actuales.map((pedido) =>
            pedido.id === id ? pedidoActualizado : pedido
          )
        );
      } else if (tipo === "manual") {
        setPedidosManuales((actuales) =>
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

      await cargarMetricas(usuario?.rol);

      return pedidoActualizado;
    } catch (requestError) {
      const mensaje = requestError.message || "No se pudo actualizar el pedido.";
      mostrarErrorEstado(mensaje);
      if (requestError.status === 409) {
        await cargarListasPedidos(restaurante);
        try {
          const detalleEndpoint = obtenerEndpointDetallePedido(tipo, id);
          const detalleResponse = await authFetch(detalleEndpoint, { cache: "no-store" });
          const pedidoReal = await readJsonResponse(
            detalleResponse,
            detalleEndpoint,
            "No se pudo refrescar el pedido."
          );
          setDetalle((actual) => (
            actual && actual.tipo === tipo && Number(actual.pedido.id) === Number(id)
              ? { ...actual, pedido: pedidoReal }
              : actual
          ));
        } catch {
          // La lista ya fue refrescada; el polling volverá a intentar el detalle.
        }
      }
      return false;
    }
  };

  const ejecutarCambioEstado = async (tipo, pedido, estado) => {
    const pedidoActualizado = await actualizarPedido(tipo, pedido.id, { estado });

    if (pedidoActualizado) {
      setDetalle((actual) => (
        actual && actual.tipo === tipo && Number(actual.pedido.id) === Number(pedido.id)
          ? { ...actual, pedido: pedidoActualizado }
          : actual
      ));
    }

    return Boolean(pedidoActualizado);
  };

  const solicitarCambioEstado = (tipo, pedido, estado) => {
    if (pedido.estado === ESTADO_CANCELADO && estado !== ESTADO_CANCELADO) return;

    if (estado === ESTADO_CANCELADO && pedido.estado !== ESTADO_CANCELADO) {
      setCancelacionPendiente({ tipo, pedido, estadoAnterior: pedido.estado });
      setCancelacionError("");
      return;
    }

    ejecutarCambioEstado(tipo, pedido, estado);
  };

  const cerrarConfirmacionCancelacion = () => {
    if (confirmandoCancelacion) return;
    setCancelacionPendiente(null);
    setCancelacionError("");
  };

  const confirmarCancelacionPedido = async () => {
    if (!cancelacionPendiente || confirmandoCancelacion) return;

    setConfirmandoCancelacion(true);
    setCancelacionError("");
    ultimoErrorEstadoRef.current = "";
    const actualizado = await ejecutarCambioEstado(
      cancelacionPendiente.tipo,
      cancelacionPendiente.pedido,
      ESTADO_CANCELADO
    );

    if (actualizado) {
      setCancelacionPendiente(null);
    } else {
      setCancelacionError(
        ultimoErrorEstadoRef.current || "No se pudo cancelar el pedido. Inténtalo nuevamente."
      );
    }
    setConfirmandoCancelacion(false);
  };

  const abrirDetalle = useCallback((tipo, pedido) => {
    setDetalle({ tipo, pedido });
    setProductoBusqueda("");
    setProductoSeleccionado("");
    setCantidadProductoNuevo(1);
    setDireccionDetalle(pedido.direccion_entrega || "");
    setDetalleItems(
      tipo === "whatsapp"
        ? (pedido.productos_snapshot || []).map((item) => ({ ...item }))
        : tipo === "manual"
          ? (pedido.items || []).map((item) => ({
              producto_id: item.producto_id,
              variante_id: item.variante_id,
              variante_nombre: item.variante_nombre || "",
              nombre: item.nombre_producto,
              precio_unitario: item.precio_unitario,
              cantidad: item.cantidad,
              subtotal: item.subtotal,
              observaciones: item.observaciones || "",
            }))
        : []
    );
  }, []);

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
      return;
    }

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
      return;
    }

    if (detalle.pedido.tipo_entrega === "delivery" && !direccionDetalle.trim()) {
      return;
    }

    const actualizado = await actualizarPedido("whatsapp", detalle.pedido.id, {
      direccion_entrega: direccionDetalle.trim(),
      productos: detalleItems.map((item) => ({
        producto_id: Number(item.producto_id),
        variante_id: item.variante_id ? Number(item.variante_id) : null,
        cantidad: Number(item.cantidad),
      })),
    });

    if (actualizado) {
      cerrarDetalle();
    }
  };

  const abrirCrearEspecial = () => {
    setPedidoEditando(null);
    setFormEspecial(formEspecialInicial);
    setMostrarFormularioEspecial(true);
  };

  const cerrarDetalle = useCallback(() => {
    setDetalle(null);
    setSearchParams((actuales) => {
      const siguientes = new URLSearchParams(actuales);
      siguientes.delete("tipo");
      siguientes.delete("pedido");
      return siguientes;
    }, { replace: true });
  }, [setSearchParams]);

  useEffect(() => {
    const tiposValidos = ["whatsapp", "manual", "especial"];
    if (loading || !tiposValidos.includes(pedidoQueryTipo) || !pedidoQueryId) return undefined;
    if (
      detalle?.tipo === pedidoQueryTipo &&
      String(detalle?.pedido?.id) === String(pedidoQueryId)
    ) return undefined;

    const pedidosPorTipo = {
      whatsapp: pedidosWhatsapp,
      manual: pedidosManuales,
      especial: pedidosEspeciales,
    };
    const pedidoCargado = pedidosPorTipo[pedidoQueryTipo]?.find(
      (pedido) => String(pedido.id) === String(pedidoQueryId)
    );

    if (pedidoCargado) {
      setTabActiva(pedidoQueryTipo === "manual" ? "menly" : pedidoQueryTipo === "especial" ? "especiales" : "whatsapp");
      abrirDetalle(pedidoQueryTipo, pedidoCargado);
      return undefined;
    }

    let cancelado = false;
    const endpoint = obtenerEndpointDetallePedido(pedidoQueryTipo, pedidoQueryId);

    const cargarDetalleEnlazado = async () => {
      try {
        const response = await authFetch(endpoint, { cache: "no-store" });
        const pedido = await readJsonResponse(
          response,
          endpoint,
          "No se pudo cargar el detalle del pedido."
        );
        if (!cancelado) {
          setTabActiva(pedidoQueryTipo === "manual" ? "menly" : pedidoQueryTipo === "especial" ? "especiales" : "whatsapp");
          abrirDetalle(pedidoQueryTipo, pedido);
        }
      } catch {
        // La URL permanece disponible para reintentar sin agregar alertas al encabezado.
      }
    };

    cargarDetalleEnlazado();
    return () => {
      cancelado = true;
    };
  }, [
    abrirDetalle,
    detalle,
    loading,
    pedidoQueryId,
    pedidoQueryTipo,
    pedidosEspeciales,
    pedidosManuales,
    pedidosWhatsapp,
  ]);

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

    const itemsValidos = formEspecial.items.every((item) =>
      String(item.nombre || "").trim() &&
      Number(item.cantidad) > 0 &&
      Number(item.precio_unitario) >= 0
    );

    if (!itemsValidos || !formEspecial.fecha_entrega || !formEspecial.nombre_cliente || !formEspecial.telefono_cliente) {
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

      await readJsonResponse(
        response,
        pedidoEditando
          ? `/mi-restaurante/pedidos/especiales/${pedidoEditando.id}/`
          : "/mi-restaurante/pedidos/especiales/",
        "No se pudo guardar el pedido especial."
      );

      setMostrarFormularioEspecial(false);
      setPedidoEditando(null);
      setFormEspecial(formEspecialInicial);
      if (!pedidoEditando) {
        paginasPedidosRef.current = { ...paginasPedidosRef.current, especiales: 1 };
      }
      await cargarPedidos(restaurante, usuario?.rol);
    } catch {
      // Conserva el formulario abierto para permitir corregir o reintentar.
    }
  };

  const categoriasManual = useMemo(() => {
    const categorias = new Map();
    catalogoProductos.forEach((producto) => {
      const categoria = producto.categoria;
      if (categoria?.id) {
        categorias.set(String(categoria.id), categoria.nombre || "Categoria");
      }
    });
    return Array.from(categorias, ([id, nombre]) => ({ id, nombre }));
  }, [catalogoProductos]);

  const productosManualFiltrados = useMemo(() => {
    const texto = productoBusquedaManual.trim().toLowerCase();
    return catalogoProductos.filter((producto) => {
      const coincideTexto = !texto || `${producto.nombre} ${producto.categoria?.nombre || ""}`.toLowerCase().includes(texto);
      const coincideCategoria = !categoriaManual || String(producto.categoria?.id) === String(categoriaManual);
      return coincideTexto && coincideCategoria;
    });
  }, [catalogoProductos, categoriaManual, productoBusquedaManual]);

  const abrirCrearManual = () => {
    setPedidoManualEditando(null);
    setFormManual(formManualInicial);
    setProductoBusquedaManual("");
    setCategoriaManual("");
    setVarianteManualSelector(null);
    setMostrarFormularioManual(true);
  };

  const cerrarFormularioManual = () => {
    setMostrarFormularioManual(false);
    setPedidoManualEditando(null);
    setVarianteManualSelector(null);
  };

  const abrirEditarManual = (pedido) => {
    setPedidoManualEditando(pedido);
    setFormManual({
      nombre_cliente: pedido.nombre_cliente || "",
      telefono_cliente: pedido.telefono_cliente || "",
      tipo_entrega: pedido.tipo_entrega || "mesa",
      direccion: pedido.direccion || "",
      numero_mesa: pedido.numero_mesa || "",
      observaciones: pedido.observaciones || "",
      items: (pedido.items || []).map((item) => {
        const producto = catalogoProductos.find(
          (catalogoItem) => Number(catalogoItem.id) === Number(item.producto_id)
        );
        return {
          producto_id: item.producto_id,
          variante_id: item.variante_id || null,
          variante_nombre: item.variante_nombre || "",
          nombre: item.nombre_producto,
          imagen: producto?.imagen || "",
          precio_unitario: Number(item.precio_unitario || 0),
          cantidad: Number(item.cantidad || 1),
          observaciones: item.observaciones || "",
        };
      }),
    });
    setProductoBusquedaManual("");
    setCategoriaManual("");
    setVarianteManualSelector(null);
    cerrarDetalle();
    setMostrarFormularioManual(true);
  };

  const agregarProductoManual = (producto, variante = null) => {
    const lineaId = claveLineaManual(producto.id, variante?.id);
    setFormManual((actual) => {
      const existente = actual.items.find((item) => claveLineaManual(item) === lineaId);
      if (existente) {
        return {
          ...actual,
          items: actual.items.map((item) => (
            claveLineaManual(item) === lineaId
              ? { ...item, cantidad: Number(item.cantidad || 0) + 1 }
              : item
          )),
        };
      }

      return {
        ...actual,
        items: [
          ...actual.items,
          {
            producto_id: producto.id,
            variante_id: variante?.id || null,
            variante_nombre: variante?.nombre || "",
            nombre: producto.nombre,
            imagen: producto.imagen || "",
            precio_unitario: Number(variante?.precio ?? producto.precio ?? 0),
            cantidad: 1,
            observaciones: "",
          },
        ],
      };
    });
  };

  const seleccionarProductoManual = (producto) => {
    const variantes = obtenerVariantesActivas(producto);
    if (variantes.length === 0) {
      agregarProductoManual(producto);
      return;
    }
    if (variantes.length === 1) {
      agregarProductoManual(producto, variantes[0]);
      return;
    }
    setVarianteManualSelector({ producto, varianteId: "" });
  };

  const confirmarVarianteManual = () => {
    if (!varianteManualSelector) return;
    const variante = obtenerVariantesActivas(varianteManualSelector.producto).find(
      (item) => String(item.id) === String(varianteManualSelector.varianteId)
    );
    if (!variante) {
      return;
    }
    agregarProductoManual(varianteManualSelector.producto, variante);
    setVarianteManualSelector(null);
  };

  const actualizarItemManual = (lineaId, cambios) => {
    setFormManual((actual) => ({
      ...actual,
      items: actual.items.map((item) => (
        claveLineaManual(item) === lineaId
          ? { ...item, ...cambios }
          : item
      )),
    }));
  };

  const cambiarCantidadManual = (lineaId, cantidad) => {
    actualizarItemManual(lineaId, { cantidad: Math.max(1, Number(cantidad) || 1) });
  };

  const quitarItemManual = (lineaId) => {
    setFormManual((actual) => ({
      ...actual,
      items: actual.items.filter((item) => claveLineaManual(item) !== lineaId),
    }));
  };

  const cambiarVarianteManual = (itemActual, varianteId) => {
    const producto = catalogoProductos.find(
      (item) => Number(item.id) === Number(itemActual.producto_id)
    );
    const variante = obtenerVariantesActivas(producto).find(
      (item) => String(item.id) === String(varianteId)
    );
    if (!producto || !variante) return;

    const lineaActualId = claveLineaManual(itemActual);
    const lineaDestinoId = claveLineaManual(producto.id, variante.id);
    setFormManual((actual) => {
      const destino = actual.items.find((item) => claveLineaManual(item) === lineaDestinoId);
      if (destino && lineaDestinoId !== lineaActualId) {
        return {
          ...actual,
          items: actual.items
            .filter((item) => claveLineaManual(item) !== lineaActualId)
            .map((item) => claveLineaManual(item) === lineaDestinoId
              ? { ...item, cantidad: Number(item.cantidad) + Number(itemActual.cantidad) }
              : item),
        };
      }
      return {
        ...actual,
        items: actual.items.map((item) => claveLineaManual(item) === lineaActualId
          ? {
              ...item,
              variante_id: variante.id,
              variante_nombre: variante.nombre,
              precio_unitario: Number(variante.precio),
            }
          : item),
      };
    });
  };

  const abrirWhatsappPedidoManual = (pedido) => {
    const telefono = normalizarTelefonoWhatsappChile(pedido?.telefono_cliente || pedido?.cliente_telefono);
    if (!telefono) {
      return;
    }

    if (!pedido?.tracking_url) {
      return;
    }

    const mensajeWhatsapp = construirMensajeWhatsappPedidoManual(pedido, restaurante);
    const url = `https://wa.me/${telefono}?text=${encodeURIComponent(mensajeWhatsapp)}`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const abrirCocina = async () => {
    if (abriendoCocina) return;

    try {
      setAbriendoCocina(true);
      const response = await authFetch("/mi-restaurante/cocina/activacion/", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      const data = await readJsonResponse(
        response,
        "/mi-restaurante/cocina/activacion/",
        "No se pudo abrir cocina."
      );
      const activationUrl = data?.activation_url;
      if (!activationUrl) {
        throw new Error("No se pudo generar el enlace de cocina.");
      }

      window.open(activationUrl, "_blank", "noopener,noreferrer");
    } catch {
      // La acción puede reintentarse desde el mismo botón sin crear un banner persistente.
    } finally {
      setAbriendoCocina(false);
    }
  };

  const abrirEditorObservacionManual = (item) => {
    setObservacionManualEditor({
      lineaId: claveLineaManual(item),
      nombre: item.nombre,
      borrador: item.observaciones || "",
    });
  };

  const cerrarEditorObservacionManual = useCallback(() => {
    const lineaId = observacionManualEditor?.lineaId;
    setObservacionManualEditor(null);
    if (lineaId) {
      window.requestAnimationFrame(() => {
        observacionManualButtonsRef.current[lineaId]?.focus();
      });
    }
  }, [observacionManualEditor?.lineaId]);

  const guardarObservacionManual = () => {
    if (!observacionManualEditor) return;
    actualizarItemManual(observacionManualEditor.lineaId, {
      observaciones: observacionManualEditor.borrador.trim(),
    });
    cerrarEditorObservacionManual();
  };

  useEffect(() => {
    if (!observacionManualEditor) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        cerrarEditorObservacionManual();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [cerrarEditorObservacionManual, observacionManualEditor]);

  const totalFormManual = formManual.items.reduce((total, item) => (
    total + Number(item.cantidad || 0) * Number(item.precio_unitario || 0)
  ), 0);

  const cantidadTotalManual = formManual.items.reduce(
    (total, item) => total + Number(item.cantidad || 0),
    0
  );
  const cantidadPedidosMenlyHoy = metricas.cantidad_pedidos_menly_hoy ?? 0;

  const pedidoManualValido =
    formManual.items.length > 0 &&
    !formManual.items.some((item) => Number(item.cantidad) < 1) &&
    (formManual.tipo_entrega !== "delivery" || Boolean(formManual.direccion.trim())) &&
    (formManual.tipo_entrega !== "mesa" || Boolean(formManual.numero_mesa.trim()));

  const cantidadProductoManual = (productoId) => (
    formManual.items
      .filter((item) => Number(item.producto_id) === Number(productoId))
      .reduce((total, item) => total + Number(item.cantidad || 0), 0)
  );

  const headerPedidoManualImagen = restaurante?.imgen_principal || restaurante?.logo || "";

  const guardarManual = async (e) => {
    e.preventDefault();
    if (guardandoManual) return;

    if (formManual.items.length === 0) {
      return;
    }

    if (formManual.items.some((item) => Number(item.cantidad) < 1)) {
      return;
    }

    if (formManual.tipo_entrega === "delivery" && !formManual.direccion.trim()) {
      return;
    }

    if (formManual.tipo_entrega === "mesa" && !formManual.numero_mesa.trim()) {
      return;
    }

    const payload = {
      nombre_cliente: formManual.nombre_cliente.trim(),
      telefono_cliente: formManual.telefono_cliente.trim(),
      tipo_entrega: formManual.tipo_entrega,
      direccion: formManual.tipo_entrega === "delivery" ? formManual.direccion.trim() : "",
      numero_mesa: formManual.tipo_entrega === "mesa" ? formManual.numero_mesa.trim() : "",
      observaciones: formManual.observaciones.trim(),
      items: formManual.items.map((item) => ({
        producto_id: Number(item.producto_id),
        variante_id: item.variante_id ? Number(item.variante_id) : null,
        cantidad: Number(item.cantidad),
        observaciones: (item.observaciones || "").trim(),
      })),
    };

    try {
      setGuardandoManual(true);
      const endpoint = pedidoManualEditando
        ? `/mi-restaurante/pedidos/manuales/${pedidoManualEditando.id}/`
        : "/mi-restaurante/pedidos/manuales/";
      const response = await authFetch(endpoint, {
        method: pedidoManualEditando ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await readJsonResponse(
        response,
        endpoint,
        pedidoManualEditando ? "No se pudo actualizar el pedido." : "No se pudo crear el pedido."
      );

      setMostrarFormularioManual(false);
      setFormManual(formManualInicial);
      setPedidoManualEditando(null);
      setTabActiva("menly");
      if (!pedidoManualEditando) {
        paginasPedidosRef.current = { ...paginasPedidosRef.current, menly: 1 };
      }
      await cargarPedidos(restaurante, usuario?.rol);
    } catch {
      // Conserva el formulario abierto para permitir corregir o reintentar.
    } finally {
      setGuardandoManual(false);
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
        <MainMenu initialData={mainMenuData} />

        <section className="reservas-page pedidos-page">
          <header className="reservas-header">
            <h1>Pedidos</h1>

            <div className="breadcrumb-reservas">
              <span>Inicio</span>
              <span>›</span>
              <strong>Pedidos</strong>
            </div>
          </header>

          {estadoError && (
            <div className="pedido-estado-error-toast" role="alert">
              {estadoError}
            </div>
          )}

          {tabsDisponibles.length === 0 ? (
            <section className="reservas-table-card">
              <p className="empty-state">El modulo de pedidos no esta activo para este restaurante.</p>
            </section>
          ) : (
            <>
              {!esEmpleado && <section className="reservas-stats pedidos-stats">
                <div className="reserva-stat-card">
                  <div className="stat-icon"><i className="bi bi-whatsapp"></i></div>
                  <div>
                    <h3>{formatearMoneda(metricas.canales?.whatsapp?.venta_real_hoy ?? 0)}</h3>
                    <p>Venta diaria WSP</p>
                    <small>{metricas.canales?.whatsapp?.pedidos_creados_hoy ?? 0} pedidos</small>
                  </div>
                </div>

                <div className="reserva-stat-card">
                  <div className="stat-icon"><i className="bi bi-calendar-heart"></i></div>
                  <div>
                    <h3>{formatearMoneda(metricas.venta_diaria_menly ?? 0)}</h3>
                    <p>Venta diaria Menly</p>
                    <small>{cantidadPedidosMenlyHoy} {cantidadPedidosMenlyHoy === 1 ? "pedido" : "pedidos"}</small>
                  </div>
                </div>

                <div className="reserva-stat-card">
                  <div className="stat-icon"><i className="bi bi-cash-stack"></i></div>
                  <div>
                    <h3>{formatearMoneda(metricas.ventas?.venta_real_mes ?? 0)}</h3>
                    <p>Venta total mes</p>
                    <small>{metricas.pedidos?.pedidos_finalizados_mes ?? 0} pedidos</small>
                  </div>
                </div>

                <div className="reserva-stat-card">
                  <div className="stat-icon"><i className="bi bi-x-circle"></i></div>
                  <div>
                    <h3>{metricas.pedidos?.pedidos_cancelados_mes ?? 0} pedidos</h3>
                    <p>Cancelados mes</p>
                  </div>
                </div>
              </section>}

              <section className="reservas-tools">
                <div className="pedidos-mobile-controls">
                  <select
                    className="mobile-menly-select pedidos-mobile-select"
                    value={tabActiva}
                    onChange={(event) => setTabActiva(event.target.value)}
                    aria-label="Seleccionar tipo de pedidos"
                  >
                    {posActivo && (
                      <option value="menly">Pedidos Menly ({paginacionPedidos.menly.count})</option>
                    )}
                    {whatsappActivo && (
                      <option value="whatsapp">Pedidos por WhatsApp ({paginacionPedidos.whatsapp.count})</option>
                    )}
                    {especialesActivo && (
                      <option value="especiales">Pedidos especiales ({paginacionPedidos.especiales.count})</option>
                    )}
                  </select>
                  <button className="crear-reserva-btn" type="button" onClick={abrirCrearManual}>
                    <i className="bi bi-plus-lg"></i>
                    Nuevo pedido
                  </button>
                  {especialesActivo && (
                    <button className="crear-reserva-btn" type="button" onClick={abrirCrearEspecial}>
                      <i className="bi bi-plus-lg"></i>
                      Nuevo pedido especial
                    </button>
                  )}
                  {puedeAbrirCocina && (
                    <button className="crear-reserva-btn pedido-cocina-btn" type="button" onClick={abrirCocina} disabled={abriendoCocina}>
                      <i className="bi bi-display"></i>
                      {abriendoCocina ? "Abriendo..." : "Abrir cocina"}
                    </button>
                  )}
                </div>

                <div className="tabs-row pedidos-tabs">
                  {posActivo && (
                    <button className={`tab ${tabActiva === "menly" ? "active" : ""}`} onClick={() => setTabActiva("menly")}>
                      Pedidos Menly ({paginacionPedidos.menly.count})
                    </button>
                  )}
                  {whatsappActivo && (
                    <button className={`tab ${tabActiva === "whatsapp" ? "active" : ""}`} onClick={() => setTabActiva("whatsapp")}>
                      Pedidos por WhatsApp ({paginacionPedidos.whatsapp.count})
                    </button>
                  )}
                  {especialesActivo && (
                    <button className={`tab ${tabActiva === "especiales" ? "active" : ""}`} onClick={() => setTabActiva("especiales")}>
                      Pedidos especiales ({paginacionPedidos.especiales.count})
                    </button>
                  )}
                  {especialesActivo && (
                    <button className="crear-reserva-btn" type="button" onClick={abrirCrearEspecial}>
                      <i className="bi bi-plus-lg"></i>
                      Nuevo pedido especial
                    </button>
                  )}
                  {posActivo && (
                    <button className="crear-reserva-btn" type="button" onClick={abrirCrearManual}>
                      <i className="bi bi-plus-lg"></i>
                      Nuevo pedido
                    </button>
                  )}
                  {puedeAbrirCocina && (
                    <button className="crear-reserva-btn pedido-cocina-btn" type="button" onClick={abrirCocina} disabled={abriendoCocina}>
                      <i className="bi bi-display"></i>
                      {abriendoCocina ? "Abriendo..." : "Abrir cocina"}
                    </button>
                  )}
                </div>
              </section>

              {posActivo && tabActiva === "menly" && (
                <section className="reservas-table-card pedido-list-card">
                  <table className="reservas-table pedidos-table">
                    <thead>
                      <tr>
                        <th>NÂ°</th>
                        <th>Origen</th>
                        <th>Cliente</th>
                        <th>Entrega</th>
                        <th>Productos</th>
                        <th>Total</th>
                        <th>Estado</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pedidosManuales.length === 0 ? (
                        <tr><td colSpan="8" className="empty-state">No hay pedidos creados desde Menly.</td></tr>
                      ) : pedidosManuales.map((pedido) => (
                        <tr className="pedido-list-row" key={pedido.id}>
                          <td className="pedido-list-numero">#{pedido.numero_pedido}</td>
                          <td className="pedido-list-extra"><span className="pedido-origen-badge">Menly</span></td>
                          <td className="pedido-list-cliente">
                            <strong>{String(pedido.nombre_cliente || "").trim() || "Cliente sin nombre"}</strong>
                          </td>
                          <td className="pedido-list-extra">
                            {pedido.tipo_entrega_display || pedido.tipo_entrega}
                            {pedido.numero_mesa && <small>Mesa {pedido.numero_mesa}</small>}
                            {pedido.direccion && <small>{pedido.direccion}</small>}
                          </td>
                          <td className="pedido-list-extra">{resumenItems(pedido.items)}</td>
                          <td className="pedido-list-total">{formatearMoneda(pedido.total)}</td>
                          <td className="pedido-list-estado"><span className={`estado-badge ${pedido.estado}`}>{estadoLabels[pedido.estado] || pedido.estado}</span></td>
                          <td className="pedido-list-controls-cell">
                            <div className="acciones-cell pedido-list-controls">
                              <button className="pedido-list-action" aria-label={`Ver pedido ${pedido.numero_pedido}`} title="Ver detalle" onClick={() => abrirDetalle("manual", pedido)}>
                                <i className="bi bi-eye"></i>
                              </button>
                              <button
                                className="pedido-list-action pedido-whatsapp-action"
                                aria-label={`Contactar por WhatsApp por el pedido ${pedido.numero_pedido}`}
                                title="Enviar por WhatsApp"
                                onClick={() => abrirWhatsappPedidoManual(pedido)}
                                disabled={!normalizarTelefonoWhatsappChile(pedido.telefono_cliente)}
                              >
                                <i className="bi bi-whatsapp"></i>
                              </button>
                              <select className="pedido-estado-select pedido-list-status-select" aria-label={`Cambiar estado del pedido ${pedido.numero_pedido}`} value={pedido.estado} onChange={(e) => solicitarCambioEstado("manual", pedido, e.target.value)}>
                                {obtenerEstadosPedidoPanel("manual", pedido).map((estado) => (
                                  <option key={estado} value={estado}>{estadoLabels[estado]}</option>
                                ))}
                              </select>
                              <button className="pedido-list-action delete" aria-label={`Cancelar pedido ${pedido.numero_pedido}`} title="Cancelar" onClick={() => solicitarCambioEstado("manual", pedido, ESTADO_CANCELADO)}>
                                <i className="bi bi-x-lg"></i>
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <PaginacionPedidos
                    paginacion={paginacionPedidos.menly}
                    onAnterior={() => cambiarPaginaPedidos("menly", paginacionPedidos.menly.page - 1)}
                    onSiguiente={() => cambiarPaginaPedidos("menly", paginacionPedidos.menly.page + 1)}
                  />
                </section>
              )}

              {tabActiva === "whatsapp" && (
                <section className="reservas-table-card pedido-list-card">
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
                        <tr className="pedido-list-row" key={pedido.id}>
                          <td className="pedido-list-numero">#{pedido.numero_pedido}</td>
                          <td className="pedido-list-cliente">
                            <strong>{String(pedido.nombre_cliente || "").trim() || "Cliente sin nombre"}</strong>
                          </td>
                          <td className="pedido-list-extra">
                            {pedido.tipo_entrega_display || pedido.tipo_entrega}
                            {pedido.direccion_entrega && <small>{pedido.direccion_entrega}</small>}
                          </td>
                          <td className="pedido-list-extra">{resumenItems(pedido.productos_snapshot)}</td>
                          <td className="pedido-list-total">{formatearMoneda(pedido.total)}</td>
                          <td className="pedido-list-estado"><span className={`estado-badge ${pedido.estado}`}>{estadoLabels[pedido.estado] || pedido.estado}</span></td>
                          <td className="pedido-list-controls-cell">
                            <div className="acciones-cell pedido-list-controls">
                              <button className="pedido-list-action" aria-label={`Ver pedido ${pedido.numero_pedido}`} title="Ver detalle" onClick={() => abrirDetalle("whatsapp", pedido)}>
                                <i className="bi bi-eye"></i>
                              </button>
                              <select className="pedido-estado-select pedido-list-status-select" aria-label={`Cambiar estado del pedido ${pedido.numero_pedido}`} value={pedido.estado} onChange={(e) => solicitarCambioEstado("whatsapp", pedido, e.target.value)}>
                                {obtenerEstadosPedidoWhatsapp(pedido).map((estado) => (
                                  <option key={estado} value={estado}>{estadoLabels[estado]}</option>
                                ))}
                              </select>
                              <button className="pedido-list-action delete" aria-label={`Cancelar pedido ${pedido.numero_pedido}`} title="Cancelar" onClick={() => solicitarCambioEstado("whatsapp", pedido, ESTADO_CANCELADO)}>
                                <i className="bi bi-x-lg"></i>
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <PaginacionPedidos
                    paginacion={paginacionPedidos.whatsapp}
                    onAnterior={() => cambiarPaginaPedidos("whatsapp", paginacionPedidos.whatsapp.page - 1)}
                    onSiguiente={() => cambiarPaginaPedidos("whatsapp", paginacionPedidos.whatsapp.page + 1)}
                  />
                </section>
              )}

              {tabActiva === "especiales" && (
                <section className="reservas-table-card pedido-list-card">
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
                        <tr className="pedido-list-row" key={pedido.id}>
                          <td className="pedido-list-numero">#{pedido.numero_pedido}</td>
                          <td className="pedido-list-cliente">
                            <strong>{String(pedido.nombre_cliente || "").trim() || "Cliente sin nombre"}</strong>
                          </td>
                          <td className="pedido-list-extra">{formatearFecha(`${pedido.fecha_entrega}T00:00:00`)}</td>
                          <td className="pedido-list-extra">{resumenItems(pedido.items, "item", "items")}</td>
                          <td className="pedido-list-total">{formatearMoneda(pedido.total)}</td>
                          <td className="pedido-list-estado"><span className={`estado-badge ${pedido.estado}`}>{estadoLabels[pedido.estado] || pedido.estado}</span></td>
                          <td className="pedido-list-controls-cell">
                            <div className="acciones-cell pedido-list-controls">
                              <button className="pedido-list-action" aria-label={`Ver pedido ${pedido.numero_pedido}`} title="Ver detalle" onClick={() => abrirDetalle("especial", pedido)}>
                                <i className="bi bi-eye"></i>
                              </button>
                              <button className="pedido-list-action" aria-label={`Editar pedido ${pedido.numero_pedido}`} title="Editar" onClick={() => abrirEditarEspecial(pedido)}>
                                <i className="bi bi-pencil-square"></i>
                              </button>
                              <select className="pedido-estado-select pedido-list-status-select" aria-label={`Cambiar estado del pedido ${pedido.numero_pedido}`} value={pedido.estado} onChange={(e) => solicitarCambioEstado("especial", pedido, e.target.value)}>
                                {obtenerEstadosPedidoPanel("especial", pedido).map((estado) => (
                                  <option key={estado} value={estado}>{estadoLabels[estado]}</option>
                                ))}
                              </select>
                              <button className="pedido-list-action delete" aria-label={`Cancelar pedido ${pedido.numero_pedido}`} title="Cancelar" onClick={() => solicitarCambioEstado("especial", pedido, ESTADO_CANCELADO)}>
                                <i className="bi bi-x-lg"></i>
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <PaginacionPedidos
                    paginacion={paginacionPedidos.especiales}
                    onAnterior={() => cambiarPaginaPedidos("especiales", paginacionPedidos.especiales.page - 1)}
                    onSiguiente={() => cambiarPaginaPedidos("especiales", paginacionPedidos.especiales.page + 1)}
                  />
                </section>
              )}
            </>
          )}
        </section>

        {detalle && (
          <div className="modal-reserva-bg">
            <section className="modal-reserva pedido-detalle-modal">
              <button className="modal-close-btn" type="button" aria-label="Cerrar" onClick={cerrarDetalle}>
                <i className="bi bi-x-lg"></i>
              </button>

              <div className="pedido-modal-header">
                <div>
                  <h2>Pedido #{detalle.pedido.numero_pedido}</h2>
                  <p className="pedido-detalle-subtitle">
                    {detalle.tipo === "whatsapp"
                      ? "Pedido por WhatsApp"
                      : detalle.tipo === "manual"
                        ? "Pedido Menly"
                        : "Pedido especial"}
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
                    {detalle.pedido.direccion && (
                      <div><dt>Direccion</dt><dd>{detalle.pedido.direccion}</dd></div>
                    )}
                    {detalle.pedido.numero_mesa && (
                      <div><dt>Mesa</dt><dd>{detalle.pedido.numero_mesa}</dd></div>
                    )}
                    {detalle.tipo === "whatsapp" && (
                      <div>
                        <dt>Pago</dt>
                        <dd>{detalle.pedido.metodo_pago_nombre || "No informado"}</dd>
                      </div>
                    )}
                    <div><dt>Estado</dt><dd>{estadoLabels[detalle.pedido.estado] || detalle.pedido.estado}</dd></div>
                    {detalle.tipo === "whatsapp" && (
                      <div className="pedido-detalle-estado-mobile">
                        <dt>Cambiar estado</dt>
                        <dd>
                          <select
                            className="pedido-estado-select"
                            value={detalle.pedido.estado}
                            onChange={(e) => solicitarCambioEstado("whatsapp", detalle.pedido, e.target.value)}
                          >
                            {obtenerEstadosPedidoWhatsapp(detalle.pedido).map((estado) => (
                              <option key={estado} value={estado}>
                                {estadoLabels[estado]}
                              </option>
                            ))}
                          </select>
                        </dd>
                      </div>
                    )}
                    {detalle.tipo === "manual" && (
                      <div className="pedido-detalle-estado-mobile">
                        <dt>Cambiar estado</dt>
                        <dd>
                          <select
                            className="pedido-estado-select"
                            value={detalle.pedido.estado}
                            onChange={(e) => solicitarCambioEstado("manual", detalle.pedido, e.target.value)}
                          >
                            {obtenerEstadosPedidoPanel("manual", detalle.pedido).map((estado) => (
                              <option key={estado} value={estado}>
                                {estadoLabels[estado]}
                              </option>
                            ))}
                          </select>
                        </dd>
                      </div>
                    )}
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
                  {detalle.pedido.observaciones && (
                    <p className="pedido-descripcion">{detalle.pedido.observaciones}</p>
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
                        <button className="button-cancelar" type="button" onClick={cerrarDetalle}>
                          Cancelar
                        </button>
                        <button type="button" onClick={guardarProductosWhatsapp}>
                          Guardar cambios
                        </button>
                      </div>
                    </>
                  ) : detalle.tipo === "manual" ? (
                    <>
                      <div className="pedido-items-detalle">
                        {(detalle.pedido.items || []).map((item, index) => (
                          <div key={`${item.producto_id}-${item.variante_id || "base"}-${index}`}>
                            <span>
                              {item.cantidad} x {item.nombre_producto}
                              {item.variante_nombre ? ` — ${item.variante_nombre}` : ""}
                            </span>
                            <small>
                              {formatearMoneda(item.precio_unitario)} c/u
                              {item.observaciones ? ` - ${item.observaciones}` : ""}
                            </small>
                            <strong>{formatearMoneda(item.subtotal)}</strong>
                          </div>
                        ))}
                      </div>
                      <div className="pedido-total-line">
                        <span>Total</span>
                        <strong>{formatearMoneda(detalle.pedido.total)}</strong>
                      </div>
                      <div className="modal-actions pedido-manual-actions">
                        <button className="button-cancelar" type="button" onClick={cerrarDetalle}>
                          Cerrar
                        </button>
                        <button type="button" onClick={() => abrirEditarManual(detalle.pedido)}>
                          <i className="bi bi-pencil-square"></i>
                          Editar pedido
                        </button>
                        <button
                          className="pedido-whatsapp-detail-btn"
                          type="button"
                          onClick={() => abrirWhatsappPedidoManual(detalle.pedido)}
                          disabled={!normalizarTelefonoWhatsappChile(detalle.pedido.telefono_cliente)}
                        >
                          <i className="bi bi-whatsapp"></i>
                          Enviar por WhatsApp
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

        {mostrarFormularioManual && (
          <div className="modal-reserva-bg pedido-manual-modal-bg">
            <form className="modal-reserva pedido-form-modal pedido-manual-modal" onSubmit={guardarManual}>
              <button className="modal-close-btn" type="button" aria-label="Cerrar" onClick={cerrarFormularioManual}>
                <i className="bi bi-x-lg"></i>
              </button>

              <div
                className="pedido-modal-header pedido-manual-header"
                style={headerPedidoManualImagen ? { "--pedido-header-image": `url("${headerPedidoManualImagen}")` } : undefined}
              >
                <div className="pedido-manual-title">
                  <span className="pedido-manual-title-icon">
                    <i className="bi bi-clipboard-check"></i>
                  </span>
                  <div>
                  <h2>{pedidoManualEditando ? "Editar pedido" : "Nuevo pedido"}</h2>
                    <p className="pedido-detalle-subtitle">
                      {pedidoManualEditando ? "Actualiza productos, variantes y cantidades" : "Selecciona productos para agregar al pedido"}
                    </p>
                  </div>
                </div>
              </div>

              <div className="pedido-manual-layout">
                <section className="pedido-form-section pedido-catalogo-manual">
                  <div className="pedido-manual-filtros">
                    <label className="pedido-manual-search">
                      <i className="bi bi-search"></i>
                      <input
                        type="search"
                        placeholder="Buscar producto..."
                        value={productoBusquedaManual}
                        onChange={(e) => setProductoBusquedaManual(e.target.value)}
                      />
                    </label>
                    <label className="pedido-manual-category">
                      <select
                        value={categoriaManual}
                        onChange={(e) => setCategoriaManual(e.target.value)}
                      >
                        <option value="">Todas las categorias</option>
                        {categoriasManual.map((categoria) => (
                          <option key={categoria.id} value={categoria.id}>{categoria.nombre}</option>
                        ))}
                      </select>
                      <i className="bi bi-chevron-down"></i>
                    </label>
                  </div>

                  <div className="pedido-productos-catalogo">
                    {productosManualFiltrados.length === 0 ? (
                      <p className="empty-state">No hay productos disponibles.</p>
                    ) : productosManualFiltrados.map((producto) => {
                      const cantidadSeleccionada = cantidadProductoManual(producto.id);
                      const tieneImagen = Boolean(producto.imagen);
                      const variantesActivas = obtenerVariantesActivas(producto);
                      const precioCatalogo = variantesActivas.length
                        ? Math.min(...variantesActivas.map((variante) => Number(variante.precio)))
                        : Number(producto.precio || 0);
                      return (
                        <button
                          type="button"
                          className={`pedido-producto-catalogo ${cantidadSeleccionada ? "is-selected" : ""} ${!tieneImagen ? "sin-imagen" : ""}`}
                          key={producto.id}
                          onClick={() => seleccionarProductoManual(producto)}
                          aria-label={`Agregar ${producto.nombre} al pedido`}
                          style={tieneImagen ? { "--producto-imagen": `url("${producto.imagen}")` } : undefined}
                        >
                          <span
                            className={`pedido-producto-thumb ${!tieneImagen ? "sin-imagen" : ""}`}
                            style={tieneImagen ? { "--producto-imagen": `url("${producto.imagen}")` } : undefined}
                            aria-hidden="true"
                          >
                            {!tieneImagen && <i className="bi bi-image"></i>}
                          </span>
                          <span className="pedido-producto-info">
                            <span className="pedido-producto-nombre">{producto.nombre}</span>
                            <strong>{variantesActivas.length ? "Desde " : ""}{formatearMoneda(precioCatalogo)}</strong>
                          </span>
                          {producto.destacado && <span className="pedido-producto-popular">Popular</span>}
                          {cantidadSeleccionada > 0 && (
                            <span className="pedido-producto-count">{cantidadSeleccionada}</span>
                          )}
                          <span className="pedido-producto-add"><i className="bi bi-plus-lg" aria-hidden="true"></i></span>
                        </button>
                      );
                    })}
                  </div>
                </section>

                <aside className="pedido-manual-side">
                  <section className="pedido-form-section pedido-manual-panel">
                    <h3><i className="bi bi-person"></i> Cliente y entrega</h3>
                    <div className="pedido-form-grid pedido-manual-client-grid">
                      <label>
                        Nombre cliente <span>(opcional)</span>
                        <input
                          type="text"
                          placeholder="Ej. Camila Soto"
                          value={formManual.nombre_cliente}
                          onChange={(e) => setFormManual({ ...formManual, nombre_cliente: e.target.value })}
                        />
                      </label>
                      <label>
                        Telefono <span>(opcional)</span>
                        <input
                          type="text"
                          placeholder="Ej. +56 9 1234 5678"
                          value={formManual.telefono_cliente}
                          onChange={(e) => setFormManual({ ...formManual, telefono_cliente: e.target.value })}
                        />
                      </label>
                      <label>
                        Tipo de entrega
                        <select
                          value={formManual.tipo_entrega}
                          onChange={(e) => setFormManual({
                            ...formManual,
                            tipo_entrega: e.target.value,
                            direccion: e.target.value === "delivery" ? formManual.direccion : "",
                            numero_mesa: e.target.value === "mesa" ? formManual.numero_mesa : "",
                          })}
                        >
                          <option value="mesa">Mesa</option>
                          <option value="retiro">Retiro</option>
                          <option value="delivery">Delivery</option>
                          <option value="para_llevar">Para llevar</option>
                        </select>
                      </label>
                      {formManual.tipo_entrega === "delivery" && (
                    <label>
                      Direccion
                      <input
                        type="text"
                        placeholder="Ej. Los Robles 123"
                        value={formManual.direccion}
                        onChange={(e) => setFormManual({ ...formManual, direccion: e.target.value })}
                        required
                      />
                    </label>
                      )}
                      {formManual.tipo_entrega === "mesa" && (
                    <label>
                      Numero de mesa
                      <input
                        type="text"
                        placeholder="Ej. 5"
                        value={formManual.numero_mesa}
                        onChange={(e) => setFormManual({ ...formManual, numero_mesa: e.target.value })}
                        required
                      />
                    </label>
                      )}
                    </div>
                    <label>
                      Observaciones generales <span>(opcional)</span>
                      <textarea
                        placeholder="Ej. Sin mayonesa, por favor"
                        value={formManual.observaciones}
                        onChange={(e) => setFormManual({ ...formManual, observaciones: e.target.value })}
                      />
                    </label>
                  </section>

                  <section className="pedido-form-section pedido-carrito-manual pedido-manual-panel">
                    <div className="pedido-carrito-header">
                      <h3><i className="bi bi-cart3"></i> Tu pedido</h3>
                      <strong>{cantidadTotalManual} productos</strong>
                    </div>
                    {formManual.items.length === 0 ? (
                      <div className="pedido-manual-empty">
                        <i className="bi bi-cart3"></i>
                        <p>Agrega productos desde la izquierda</p>
                      </div>
                    ) : (
                      <div className="pedido-manual-items">
                        {formManual.items.map((item) => {
                          const lineaId = claveLineaManual(item);
                          const productoCatalogo = catalogoProductos.find(
                            (producto) => Number(producto.id) === Number(item.producto_id)
                          );
                          const variantesActivas = obtenerVariantesActivas(productoCatalogo);
                          return (
                          <article className="pedido-manual-item" key={lineaId}>
                            <div className={`pedido-manual-item-img ${!item.imagen ? "sin-imagen" : ""}`}>
                              {item.imagen ? (
                                <img src={item.imagen} alt={item.nombre} loading="lazy" />
                              ) : (
                                <i className="bi bi-image"></i>
                              )}
                            </div>
                            <div className="pedido-manual-item-main">
                              <strong>{item.nombre}{item.variante_nombre ? ` — ${item.variante_nombre}` : ""}</strong>
                              <small>{formatearMoneda(item.precio_unitario)} c/u</small>
                              {variantesActivas.length > 1 && (
                                <label className="pedido-manual-variante-inline">
                                  <span>Variante</span>
                                  <select
                                    value={item.variante_id || ""}
                                    onChange={(e) => cambiarVarianteManual(item, e.target.value)}
                                  >
                                    {variantesActivas.map((variante) => (
                                      <option key={variante.id} value={variante.id}>
                                        {variante.nombre} — {formatearMoneda(variante.precio)}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                              )}
                            </div>
                            <div className="pedido-cantidad-control">
                              <button type="button" onClick={() => cambiarCantidadManual(lineaId, Number(item.cantidad) - 1)}>
                                <i className="bi bi-dash"></i>
                              </button>
                              <input
                                type="number"
                                min="1"
                                value={item.cantidad}
                                onChange={(e) => cambiarCantidadManual(lineaId, e.target.value)}
                              />
                              <button type="button" onClick={() => cambiarCantidadManual(lineaId, Number(item.cantidad) + 1)}>
                                <i className="bi bi-plus"></i>
                              </button>
                            </div>
                            <strong>{formatearMoneda(Number(item.cantidad || 0) * Number(item.precio_unitario || 0))}</strong>
                            <div className="pedido-manual-item-actions">
                              <button
                                type="button"
                                className={`pedido-icon-observacion ${item.observaciones ? "has-note" : ""}`}
                                onClick={() => abrirEditorObservacionManual(item)}
                                aria-label={`${item.observaciones ? "Editar observacion de" : "Agregar observacion a"} ${item.nombre}`}
                                title={item.observaciones ? item.observaciones : "Agregar observacion"}
                                ref={(node) => {
                                  if (node) {
                                    observacionManualButtonsRef.current[lineaId] = node;
                                  }
                                }}
                              >
                                <i className={item.observaciones ? "bi bi-chat-left-text-fill" : "bi bi-chat-left-text"}></i>
                              </button>
                              <button type="button" className="pedido-icon-danger" onClick={() => quitarItemManual(lineaId)} aria-label={`Eliminar ${item.nombre}`}>
                                <i className="bi bi-trash"></i>
                              </button>
                            </div>
                          </article>
                          );
                        })}
                      </div>
                    )}

                  </section>
                </aside>
              </div>

              <div className="pedido-manual-footer">
                <div className="pedido-manual-footer-summary">
                  <span>{cantidadTotalManual} productos seleccionados</span>
                  <strong>Total: <b>{formatearMoneda(totalFormManual)}</b></strong>
                </div>
                <div className="modal-actions">
                  <button className="button-cancelar" type="button" onClick={cerrarFormularioManual}>
                    Cancelar
                  </button>
                  <button type="submit" disabled={guardandoManual || !pedidoManualValido}>
                    <i className="bi bi-check-circle"></i>
                    {guardandoManual
                      ? (pedidoManualEditando ? "Guardando..." : "Creando...")
                      : (pedidoManualEditando ? "Guardar cambios" : "Confirmar pedido")}
                  </button>
                </div>
              </div>

              {varianteManualSelector && (
                <div className="pedido-observacion-backdrop pedido-variante-backdrop" role="dialog" aria-modal="true" aria-labelledby="pedido-variante-title">
                  <section className="pedido-variante-modal">
                    <div className="pedido-variante-header">
                      <div>
                        <p>Producto</p>
                        <h3 id="pedido-variante-title">{varianteManualSelector.producto.nombre}</h3>
                      </div>
                      <button type="button" aria-label="Cerrar selector de variante" onClick={() => setVarianteManualSelector(null)}>
                        <i className="bi bi-x-lg"></i>
                      </button>
                    </div>

                    <p className="pedido-variante-instruccion">Selecciona una variante</p>
                    <div className="pedido-variante-opciones">
                      {obtenerVariantesActivas(varianteManualSelector.producto).map((variante) => (
                        <label className="pedido-variante-opcion" key={variante.id}>
                          <input
                            type="radio"
                            name="pedido-variante-manual"
                            value={variante.id}
                            checked={String(varianteManualSelector.varianteId) === String(variante.id)}
                            onChange={(e) => setVarianteManualSelector((actual) => (
                              actual ? { ...actual, varianteId: e.target.value } : actual
                            ))}
                          />
                          <span>
                            <strong>{variante.nombre}</strong>
                            {variante.descripcion && <small>{variante.descripcion}</small>}
                          </span>
                          <b>{formatearMoneda(variante.precio)}</b>
                        </label>
                      ))}
                    </div>

                    <div className="modal-actions">
                      <button className="button-cancelar" type="button" onClick={() => setVarianteManualSelector(null)}>
                        Cancelar
                      </button>
                      <button type="button" disabled={!varianteManualSelector.varianteId} onClick={confirmarVarianteManual}>
                        Agregar
                      </button>
                    </div>
                  </section>
                </div>
              )}

              {observacionManualEditor && (
                <div className="pedido-observacion-backdrop" role="dialog" aria-modal="true">
                  <section className="pedido-observacion-modal">
                    <div className="pedido-observacion-header">
                      <div>
                        <p>Observacion del producto</p>
                        <h3>{observacionManualEditor.nombre}</h3>
                      </div>
                      <button type="button" aria-label="Cerrar observacion" onClick={cerrarEditorObservacionManual}>
                        <i className="bi bi-x-lg"></i>
                      </button>
                    </div>
                    <textarea
                      maxLength={250}
                      value={observacionManualEditor.borrador}
                      placeholder="Ej: sin cebolla, salsa aparte, bien cocido"
                      onChange={(e) => setObservacionManualEditor((actual) => (
                        actual ? { ...actual, borrador: e.target.value } : actual
                      ))}
                      autoFocus
                    />
                    <div className="pedido-observacion-counter">
                      {observacionManualEditor.borrador.length}/250
                    </div>
                    <div className="modal-actions">
                      <button className="button-cancelar" type="button" onClick={cerrarEditorObservacionManual}>
                        Cancelar
                      </button>
                      <button type="button" onClick={guardarObservacionManual}>
                        Guardar observacion
                      </button>
                    </div>
                  </section>
                </div>
              )}
            </form>
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
        <ConfirmarCancelacionPedido
          abierto={Boolean(cancelacionPendiente)}
          cargando={confirmandoCancelacion}
          error={cancelacionError}
          onVolver={cerrarConfirmacionCancelacion}
          onConfirmar={confirmarCancelacionPedido}
        />
      </main>
    </div>
  );
}
