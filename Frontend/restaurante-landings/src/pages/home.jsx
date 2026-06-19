import { useEffect, useRef, useState } from "react";
import Menu from "../components/Menu";
import { useParams } from "react-router-dom";
import ReservaForm from "../components/ReservaForm";
import SolicitudEspecialForm from "../components/SolicitudEspecialForm";
import WhatsAppFloatingButton from "../components/WhatsAppFloatingButton";
import { apiFetch, BASE_URL } from "../Services/api";
import { getSlugFromHostname } from "../utils/getSlugFromHostname";
import { getOptimizedImageUrl } from "../utils/images";
import "../themes/themes.css";
import { GiFireBowl } from "react-icons/gi";

const CLOUDINARY_BASE = import.meta.env.VITE_CLOUDINARY_BASE;
const MENU_CACHE_TTL = 60 * 5 * 1000;

const upsertMetaTag = (selector, attributes) => {
  let meta = document.querySelector(selector);

  if (!meta) {
    meta = document.createElement("meta");
    document.head.appendChild(meta);
  }

  Object.entries(attributes).forEach(([key, value]) => {
    meta.setAttribute(key, value);
  });
};

const getAbsoluteUrl = (url) => {
  if (!url) return "";

  return new URL(url, window.location.origin).href;
};

const upsertLinkTag = (selector, attributes) => {
  let link = document.querySelector(selector);

  if (!link) {
    link = document.createElement("link");
    document.head.appendChild(link);
  }

  Object.entries(attributes).forEach(([key, value]) => {
    link.setAttribute(key, value);
  });
};

const upsertJsonLd = (id, data) => {
  let script = document.getElementById(id);

  if (!script) {
    script = document.createElement("script");
    script.type = "application/ld+json";
    script.id = id;
    document.head.appendChild(script);
  }

  script.textContent = JSON.stringify(data);
};

const getCachedMenu = (slug) => {
  try {
    const cached = localStorage.getItem(`menu_${slug}`);
    if (!cached) return null;

    const parsed = JSON.parse(cached);
    if (Date.now() - parsed.timestamp > MENU_CACHE_TTL) {
      localStorage.removeItem(`menu_${slug}`);
      return null;
    }

    return parsed.data;
  } catch {
    localStorage.removeItem(`menu_${slug}`);
    return null;
  }
};

const setCachedMenu = (slug, data) => {
  localStorage.setItem(
    `menu_${slug}`,
    JSON.stringify({
      timestamp: Date.now(),
      data,
    })
  );
};

const getCategoriasFromMenuResponse = (menuResponse) =>
  Array.isArray(menuResponse) ? menuResponse : menuResponse?.categorias || [];

const getRestauranteFlagsFromMenuResponse = (menuResponse) =>
  Array.isArray(menuResponse) ? {} : menuResponse?.restaurante || {};

const MAX_UNIDADES_POR_PRODUCTO = 5;

export default function Home() {
  const { slug: routeSlug } = useParams();
  const hostnameSlug = getSlugFromHostname();
  const slug = hostnameSlug || routeSlug || "demo-menly";
  
  const [restaurante, setRestaurante] = useState(null);
  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [selectedPromotion, setSelectedPromotion] = useState(null);
  const [selectedGalleryImage, setSelectedGalleryImage] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [solicitudMensaje, setSolicitudMensaje] = useState("");
  const [solicitudError, setSolicitudError] = useState("");
  const [solicitudEnviando, setSolicitudEnviando] = useState(false);
  const [restauranteInactivo, setRestauranteInactivo] = useState(null);
  const [carrito, setCarrito] = useState([]);
  const [pedidoMensaje, setPedidoMensaje] = useState("");
  const [pedidoError, setPedidoError] = useState("");
  const [pedidoEnviando, setPedidoEnviando] = useState(false);
  const [carritoAbierto, setCarritoAbierto] = useState(false);
  const [tipoEntregaPedido, setTipoEntregaPedido] = useState("");
  const [mostrarCarritoFlotante, setMostrarCarritoFlotante] = useState(false);
  const [cantidadPromocion, setCantidadPromocion] = useState(1);
  const [toastCarrito, setToastCarrito] = useState("");
  const [modalActivo, setModalActivo] = useState(null);
  const [destacadosIndex, setDestacadosIndex] = useState(0);
  const [destacadosPorVista, setDestacadosPorVista] = useState(3);
  const [destacadosOffset, setDestacadosOffset] = useState(0);
  const promocionesCarouselRef = useRef(null);
  const destacadosCarouselRef = useRef(null);

  useEffect(() => {
    if (!slug) {
      setLoading(false);
      return;
    }

    const fetchData = async () => {
      try {
        //const cachedMenu = getCachedMenu(slug);
        //if (cachedMenu) {
        //  setCategorias(getCategoriasFromMenuResponse(cachedMenu));
        //}

        const [dataRestaurante, dataMenu] = await Promise.all([
          apiFetch(`/restaurantes/${slug}/?t=${Date.now()}`),
          apiFetch(`/menu/${slug}/?t=${Date.now()}`),
        ]);

        if (
          dataRestaurante?.estado === "inactivo" ||
          dataMenu?.estado === "inactivo"
        ) {
          localStorage.removeItem(`menu_${slug}`);
          setRestauranteInactivo(dataRestaurante?.estado === "inactivo" ? dataRestaurante : dataMenu);
          return;
        }

        const categoriasMenu = getCategoriasFromMenuResponse(dataMenu);
        setRestaurante({
          ...dataRestaurante,
          ...getRestauranteFlagsFromMenuResponse(dataMenu),
        });
        setCategorias(categoriasMenu);
        //setCachedMenu(slug, dataMenu);
      } catch (error) {
        const payload = error?.payload;
        if (error?.status === 403 && payload?.estado === "inactivo") {
          localStorage.removeItem(`menu_${slug}`);
          setRestauranteInactivo(payload);
        } else {
          setError("No pudimos cargar el restaurante. Revisa tu conexion e intenta nuevamente.");
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [slug]);

  const handleClickProducto = async (id) => {
    try {
      await apiFetch(`/productos/${id}/click/`, {
        method: "POST",
        retries: 0,
      });
    } catch {

    }
  };

  const getProductConditions = (producto) =>
    producto?.condiciones ||
    producto?.condicion ||
    producto?.terminos ||
    producto?.terminos_condiciones ||
    producto?.restricciones ||
    producto?.detalle_promocion ||
    "";

  const hasProductImage = (producto) =>
    Boolean(producto?.imagen_url || producto?.imagen || producto?.foto_url || producto?.foto);

  const getProductImage = (producto, size = {}) => {
    const image =
      producto?.imagen_url ||
      producto?.imagen ||
      producto?.foto_url ||
      producto?.foto;

    const fallbackImage =
      restaurante?.logo_url ||
      (restaurante?.imgen_principal
        ? getOptimizedImageUrl(restaurante.imgen_principal, {
            baseUrl: CLOUDINARY_BASE,
            width: size.width || 800,
            height: size.height || 600,
          })
        : "/favicon.svg");

    return getOptimizedImageUrl(image, {
      baseUrl: CLOUDINARY_BASE,
      fallbackImage,
      width: size.width || 800,
      height: size.height || 600,
    });
  };

  const handlePromotionClick = (producto) => {
    handleClickProducto(producto.id);
    setCantidadPromocion(1);
    setSelectedPromotion(producto);
  };

  const mostrarToastCarrito = (mensaje) => {
    setToastCarrito(mensaje);
    window.clearTimeout(window.menlyCartToastTimer);
    window.menlyCartToastTimer = window.setTimeout(() => {
      setToastCarrito("");
    }, 2600);
  };

  const agregarAlCarrito = (producto, cantidad = 1) => {
    let agregado = false;
    let maximoAlcanzado = false;

    setPedidoMensaje("");
    setPedidoError("");
    setCarrito((items) => {
      const existente = items.find((item) => item.producto_id === producto.id);
      const cantidadSegura = Math.min(
        MAX_UNIDADES_POR_PRODUCTO,
        Math.max(1, Number(cantidad) || 1)
      );

      if (existente) {
        const nuevaCantidad = Math.min(
          MAX_UNIDADES_POR_PRODUCTO,
          existente.cantidad + cantidadSegura
        );
        maximoAlcanzado = nuevaCantidad === existente.cantidad;
        agregado = nuevaCantidad > existente.cantidad;

        return items.map((item) =>
          item.producto_id === producto.id
            ? { ...item, cantidad: nuevaCantidad }
            : item
        );
      }

      agregado = true;
      return [
        ...items,
        {
          producto_id: producto.id,
          nombre: producto.nombre,
          precio: Number(producto.precio),
          cantidad: cantidadSegura,
        },
      ];
    });

    mostrarToastCarrito(
      agregado ? "Producto agregado al carrito" : "Máximo 5 unidades por producto"
    );
  };

  const cambiarCantidadCarrito = (productoId, delta) => {
    setCarrito((items) =>
      items
        .map((item) =>
          item.producto_id === productoId
            ? {
                ...item,
                cantidad: Math.min(
                  MAX_UNIDADES_POR_PRODUCTO,
                  item.cantidad + delta
                ),
              }
            : item
        )
        .filter((item) => item.cantidad > 0)
    );
  };

  const eliminarDelCarrito = (productoId) => {
    setCarrito((items) => items.filter((item) => item.producto_id !== productoId));
  };

  const totalCarrito = carrito.reduce(
    (total, item) => total + item.precio * item.cantidad,
    0
  );
  const totalUnidadesCarrito = carrito.reduce((total, item) => total + item.cantidad, 0);

  const handlePedidoWhatsApp = async (e) => {
    e.preventDefault();
    if (pedidoEnviando) return;

    const form = e.currentTarget;
    const formData = new FormData(form);
    const data = {
      nombre_cliente: String(formData.get("nombre_cliente") || "").trim(),
      telefono_cliente: String(formData.get("telefono_cliente") || "").trim(),
      tipo_entrega: formData.get("tipo_entrega"),
      direccion_entrega: String(formData.get("direccion_entrega") || "").trim(),
      productos: carrito.map((item) => ({
        producto_id: item.producto_id,
        cantidad: item.cantidad,
      })),
    };

    setPedidoMensaje("");
    setPedidoError("");

    if (carrito.length === 0) {
      setPedidoError("Agrega al menos un producto para enviar el pedido.");
      return;
    }

    if (!data.nombre_cliente || !data.telefono_cliente || !data.tipo_entrega) {
      setPedidoError("Completa tu nombre, teléfono y tipo de entrega.");
      return;
    }

    if (data.tipo_entrega === "delivery" && !data.direccion_entrega) {
      setPedidoError("Debe ingresar una dirección para delivery.");
      return;
    }

    setPedidoEnviando(true);

    try {
      const pedido = await apiFetch(`/pedidos-whatsapp/${slug}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
        retries: 0,
      });

      setPedidoMensaje("Pedido guardado correctamente. Se abrirá WhatsApp para enviarlo.");
      setCarrito([]);
      setCarritoAbierto(false);
      setTipoEntregaPedido("");
      form.reset();
      window.open(pedido.whatsapp_url, "_blank", "noopener,noreferrer");
    } catch (requestError) {
      const apiMessage =
        requestError?.payload?.error ||
        requestError?.payload?.detail ||
        requestError?.payload?.carrito ||
        requestError?.payload?.productos ||
        requestError?.payload?.non_field_errors?.[0] ||
        "No se pudo guardar el pedido. Intenta nuevamente.";
      setPedidoError(Array.isArray(apiMessage) ? apiMessage[0] : apiMessage);
    } finally {
      setPedidoEnviando(false);
    }
  };

  const renderBotonCarrito = (className = "") => (
    <button
      type="button"
      className={`cart-trigger ${className}`.trim()}
      onClick={() => setCarritoAbierto(true)}
      aria-label={`Abrir carrito, ${totalUnidadesCarrito} productos`}
    >
      <i className="bi bi-basket2-fill" aria-hidden="true"></i>
      <span>Carrito</span>
      <strong>{totalUnidadesCarrito}</strong>
    </button>
  );

  const handleReserva = async (e) => {
    e.preventDefault();
    if (enviando) return;

    const form = e.currentTarget;
    setMensaje("");
    setError("");
    setEnviando(true);

    const formData = new FormData(form);

    const data = {
      nombre_cliente: formData.get("nombre_cliente"),
      telefono: formData.get("telefono"),
      email: formData.get("email"),
      fecha: formData.get("fecha"),
      hora: formData.get("hora"),
      cantidad_personas: Number(formData.get("cantidad_personas")),
      mensaje: formData.get("mensaje") || "",
    };

    try {
      await apiFetch(`/reservas/${slug}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
        retries: 0,
      });

      setMensaje("Reserva enviada correctamente. Te contactaremos para confirmar.");
      form.reset();
    } catch (requestError) {
      const apiMessage =
        requestError?.payload?.error ||
        requestError?.payload?.detail ||
        "No se pudo enviar la reserva. Intenta nuevamente.";
      setError(apiMessage);
    } finally {
      setEnviando(false);
    }
  };

  const handleSolicitudEspecial = async (e) => {
    e.preventDefault();
    if (solicitudEnviando) return;

    const form = e.currentTarget;
    const formData = new FormData(form);

    setSolicitudMensaje("");
    setSolicitudError("");

    const data = {
      restaurante_id: restaurante?.id,
      nombre: String(formData.get("nombre") || "").trim(),
      apellido: String(formData.get("apellido") || "").trim(),
      fecha_evento: formData.get("fecha_evento"),
      telefono_contacto: String(formData.get("telefono_contacto") || "").trim(),
      email_contacto: String(formData.get("email_contacto") || "").trim(),
      descripcion_solicitud: String(formData.get("descripcion_solicitud") || "").trim(),
    };

    const camposRequeridos = [
      "nombre",
      "apellido",
      "fecha_evento",
      "telefono_contacto",
      "email_contacto",
      "descripcion_solicitud",
    ];
    const campoVacio = camposRequeridos.some((field) => !data[field]);

    if (!data.restaurante_id) {
      setSolicitudError("No se pudo identificar el restaurante. Recarga la página e intenta nuevamente.");
      return;
    }

    if (campoVacio) {
      setSolicitudError("Completa todos los campos para enviar la solicitud.");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email_contacto)) {
      setSolicitudError("Ingresa un email válido.");
      return;
    }

    setSolicitudEnviando(true);

    try {
      await apiFetch(`/solicitudes-especiales/${slug}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
        retries: 0,
      });

      setSolicitudMensaje("Solicitud enviada. El restaurante se pondrá en contacto contigo.");
      form.reset();
    } catch (requestError) {
      const apiMessage =
        requestError?.payload?.error ||
        requestError?.payload?.detail ||
        "Error al enviar la solicitud.";
      setSolicitudError(apiMessage);
    } finally {
      setSolicitudEnviando(false);
    }
  };

  const getCategoryName = (cat) => cat?.categoria || cat?.nombre || "";
  const normalizeText = (value = "") =>
    String(value)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim();
  const isFeaturedProduct = (producto) =>
    producto?.destacado === true ||
    producto?.destacado === "true" ||
    producto?.destacado === 1 ||
    producto?.destacado === "1";
  const isPromotionCategory = (cat) =>
    normalizeText(getCategoryName(cat)) === "promociones";

  const categoriaPromociones = categorias.find(isPromotionCategory);

  const promociones = (categoriaPromociones?.productos || []).filter(isFeaturedProduct);

  const productosDestacados = categorias
    .filter((cat) => !isPromotionCategory(cat))
    .flatMap((cat) =>
      (cat?.productos || [])
        .filter(isFeaturedProduct)
        .map((producto) => ({
          ...producto,
          categoriaNombre: getCategoryName(cat) || "Sin categoría",
        }))
    );
  const destacadosVisibles = Math.min(Math.max(productosDestacados.length, 1), destacadosPorVista);
  const destacadosConCarrusel = productosDestacados.length > 3;
  const destacadosMaxIndex = Math.max(0, productosDestacados.length - destacadosVisibles);

  const imagenesRestaurante = (restaurante?.imagenes || [])
    .filter((imagen) => Boolean(imagen?.url))
    .sort((a, b) => (a?.orden || 0) - (b?.orden || 0));

  const logoOptimizado = getOptimizedImageUrl(restaurante?.logo_url, {
    baseUrl: CLOUDINARY_BASE,
    fallbackImage: "",
    width: 160,
    height: 160,
  });
  const imagenPrincipalOptimizada = getOptimizedImageUrl(restaurante?.imgen_principal, {
    baseUrl: CLOUDINARY_BASE,
    fallbackImage: "",
    width: 1200,
    height: 900,
  });
  const imagenFormularioOptimizada = getOptimizedImageUrl(restaurante?.imgen_form, {
    baseUrl: CLOUDINARY_BASE,
    fallbackImage: "/img/default.jpg",
    width: 1000,
    height: 800,
  });

  useEffect(() => {
    if (BASE_URL) {
      try {
        const apiOrigin = new URL(BASE_URL, window.location.origin).origin;
        upsertLinkTag(`link[rel="preconnect"][href="${apiOrigin}"]`, {
          rel: "preconnect",
          href: apiOrigin,
        });
      } catch {
        // Invalid API URL is handled by apiFetch when requests are made.
      }
    }

    if (CLOUDINARY_BASE) {
      try {
        const cloudinaryOrigin = new URL(CLOUDINARY_BASE, window.location.origin).origin;
        upsertLinkTag(`link[rel="preconnect"][href="${cloudinaryOrigin}"]`, {
          rel: "preconnect",
          href: cloudinaryOrigin,
        });
      } catch {
        // Optional optimization only.
      }
    }
  }, []);

  useEffect(() => {
    if (!restaurante?.nombre_empresa) return;

    const nombre = restaurante.nombre_empresa;
    const descripcion =
      restaurante.descripcion ||
      `Revisa el menú de ${nombre}, descubre nuestros platos y realiza tu reserva online.`;
    const ogImage = getAbsoluteUrl(
      logoOptimizado || imagenPrincipalOptimizada || "/favicon.svg"
    );

    document.title = `${nombre} | Menú Digital`;

    upsertMetaTag('meta[name="description"]', {
      name: "description",
      content: descripcion,
    });
    upsertMetaTag('meta[property="og:title"]', {
      property: "og:title",
      content: `${nombre} | Menú Digital`,
    });
    upsertMetaTag('meta[property="og:description"]', {
      property: "og:description",
      content: descripcion,
    });
    upsertMetaTag('meta[property="og:image"]', {
      property: "og:image",
      content: ogImage,
    });
    upsertMetaTag('meta[property="og:url"]', {
      property: "og:url",
      content: window.location.href,
    });
    upsertMetaTag('meta[property="og:type"]', {
      property: "og:type",
      content: "restaurant",
    });
    upsertMetaTag('meta[name="twitter:card"]', {
      name: "twitter:card",
      content: "summary_large_image",
    });
    upsertMetaTag('meta[name="twitter:title"]', {
      name: "twitter:title",
      content: `${nombre} | Menú Digital`,
    });
    upsertMetaTag('meta[name="twitter:description"]', {
      name: "twitter:description",
      content: descripcion,
    });
    upsertMetaTag('meta[name="twitter:image"]', {
      name: "twitter:image",
      content: ogImage,
    });
    upsertLinkTag('link[rel="canonical"]', {
      rel: "canonical",
      href: window.location.href.split("#")[0],
    });
    upsertJsonLd("menly-restaurant-jsonld", {
      "@context": "https://schema.org",
      "@type": "Restaurant",
      name: nombre,
      description: descripcion,
      image: ogImage,
      address: `${restaurante.direccion || ""}, ${restaurante.ciudad || ""}`.trim(),
      telephone: restaurante.telefono || restaurante.whatsapp || "",
      url: window.location.href.split("#")[0],
      servesCuisine: "Restaurant",
      hasMenu: `${window.location.href.split("#")[0]}#menu`,
    });
  }, [imagenPrincipalOptimizada, logoOptimizado, restaurante]);

  useEffect(() => {
    const startAutoScroll = (carousel, delay) => {
      if (!carousel) return null;

      return setInterval(() => {
        const reachedEnd =
          carousel.scrollLeft + carousel.clientWidth >= carousel.scrollWidth - 8;

        carousel.scrollTo({
          left: reachedEnd ? 0 : carousel.scrollLeft + carousel.clientWidth,
          behavior: "smooth",
        });
      }, delay);
    };

    const promocionesTimer =
      promociones.length > 1
        ? startAutoScroll(promocionesCarouselRef.current, 10000)
        : null;

    return () => {
      if (promocionesTimer) clearInterval(promocionesTimer);
    };
  }, [promociones.length]);

  useEffect(() => {
    const actualizarDestacadosPorVista = () => {
      if (window.innerWidth <= 640) {
        setDestacadosPorVista(1);
        return;
      }

      if (window.innerWidth <= 900) {
        setDestacadosPorVista(2);
        return;
      }

      setDestacadosPorVista(3);
    };

    actualizarDestacadosPorVista();
    window.addEventListener("resize", actualizarDestacadosPorVista);

    return () => {
      window.removeEventListener("resize", actualizarDestacadosPorVista);
    };
  }, []);

  useEffect(() => {
    setDestacadosIndex((actual) => Math.min(actual, destacadosMaxIndex));
  }, [destacadosMaxIndex]);

  useEffect(() => {
    const actualizarOffsetDestacados = () => {
      const carousel = destacadosCarouselRef.current;
      const track = carousel?.querySelector(".featured-track");
      const slide = carousel?.querySelector(".featured-slide");

      if (!track || !slide) {
        setDestacadosOffset(0);
        return;
      }

      const gap = Number.parseFloat(window.getComputedStyle(track).gap) || 0;
      const slideWidth = slide.getBoundingClientRect().width;
      setDestacadosOffset(destacadosIndex * (slideWidth + gap));
    };

    actualizarOffsetDestacados();
    window.addEventListener("resize", actualizarOffsetDestacados);

    return () => {
      window.removeEventListener("resize", actualizarOffsetDestacados);
    };
  }, [destacadosIndex, destacadosVisibles, productosDestacados.length]);

  useEffect(() => {
    if (!destacadosConCarrusel) return undefined;

    const destacadosTimer = setInterval(() => {
      setDestacadosIndex((actual) => (
        actual >= destacadosMaxIndex
          ? 0
          : Math.min(actual + destacadosVisibles, destacadosMaxIndex)
      ));
    }, 8000);

    return () => clearInterval(destacadosTimer);
  }, [destacadosConCarrusel, destacadosMaxIndex, destacadosVisibles]);

  useEffect(() => {
    if (!selectedPromotion) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setSelectedPromotion(null);
      }
    };

    document.body.classList.add("modal-open");
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.classList.remove("modal-open");
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [selectedPromotion]);

  useEffect(() => {
    const handleScroll = () => {
      setMostrarCarritoFlotante(window.scrollY > 96);
    };

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  useEffect(() => {
    if (!carritoAbierto) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setCarritoAbierto(false);
      }
    };

    document.body.classList.add("modal-open");
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.classList.remove("modal-open");
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [carritoAbierto]);

  useEffect(() => {
    if (!modalActivo) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setModalActivo(null);
      }
    };

    document.body.classList.add("modal-open");
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.classList.remove("modal-open");
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [modalActivo]);

  useEffect(() => {
    document.body.classList.toggle("mobile-nav-open", mobileNavOpen);

    return () => {
      document.body.classList.remove("mobile-nav-open");
    };
  }, [mobileNavOpen]);

  if (loading) {
    return (
      <div className="page-shell loading-screen">
        <div className="skeleton-card" aria-label="Cargando menú"></div>
      </div>
    );
  }

  if (!slug) {
    return (
      <div className="page-shell inactive-restaurant-screen">
        <section className="inactive-restaurant-card">
          <span className="inactive-restaurant-kicker">Menú no disponible</span>
          <h1>No encontramos un restaurante para este dominio.</h1>
          <p>
            Ingresa desde el subdominio asignado a tu restaurante o usa un enlace válido.
          </p>
        </section>
      </div>
    );
  }

  if (restauranteInactivo) {
    return (
      <div className="page-shell inactive-restaurant-screen">
        <section className="inactive-restaurant-card">
          <span className="inactive-restaurant-kicker">Menú temporalmente no disponible</span>
          <h1>Este restaurante se encuentra temporalmente inactivo.</h1>
          <p>
            El propietario debe regularizar su suscripción para volver a activar el menú digital.
          </p>
          <small>{restauranteInactivo.detalle}</small>
        </section>
      </div>
    );
  }

  const allowedThemes = ["theme_1", "theme_2", "theme_3", "theme_4", "theme_5", "theme_6", "theme_7", "theme_8", "theme_9"];
  const themeClass = allowedThemes.includes(restaurante?.theme_color)
    ? restaurante.theme_color
    : "theme_1";
  const reservasActivas = restaurante?.reservas_activas === true;
  const solicitudesEspecialesActivas = restaurante?.solicitudes_especiales_activas === true;
  const carritoWhatsappActivo = restaurante?.carrito_whatsapp_activo === true;
  const destacadosClase = [
    "featured-carousel",
    destacadosConCarrusel ? "is-carousel" : "is-static",
    `featured-count-${destacadosVisibles}`,
  ].join(" ");

  const abrirModalAccion = (tipo) => {
    setMobileNavOpen(false);
    setModalActivo(tipo);
  };

  const moverDestacados = (direccion) => {
    setDestacadosIndex((actual) => {
      const siguiente = actual + direccion * destacadosVisibles;

      if (siguiente < 0) return destacadosMaxIndex;
      if (siguiente > destacadosMaxIndex) return 0;
      return siguiente;
    });
  };
  console.log("routeSlug:", routeSlug);
  console.log("hostnameSlug:", hostnameSlug);
  console.log("slug final:", slug);
  console.log("URL API:", `${BASE_URL}/menu/${slug}/`);
  console.log("restaurante", restaurante);
  console.log("carrito_whatsapp_activo", restaurante?.carrito_whatsapp_activo);
  return (
    <div
      className={`page-shell ${themeClass}`}
      style={{
        "--img-principal-base-restaurante": restaurante?.imgen_principal
          ? `url(${imagenPrincipalOptimizada})`
          : "none",
      }}
    >
      <header className="site-header">
        <button
          type="button"
          className="mobile-menu-toggle"
          aria-label={mobileNavOpen ? "Cerrar menú" : "Abrir menú"}
          aria-expanded={mobileNavOpen}
          onClick={() => setMobileNavOpen((isOpen) => !isOpen)}
        >
          <span></span>
          <span></span>
          <span></span>
        </button>

        <div className="brand-block">
          {logoOptimizado && (
            <img
              src={logoOptimizado}
              alt={restaurante.nombre_empresa}
              className="brand-logo"
              loading="lazy"
              width="64"
              height="64"
            />
          )}
          <div className="span-info-brand-block">
            <span className="brand-name">{restaurante?.nombre_empresa || "Restaurante"}</span>
            <span className="brand-tag">{restaurante?.ciudad || "Bienvenido"}</span>
          </div>
          
        </div>

        <nav className={`site-nav ${mobileNavOpen ? "is-open" : ""}`}>
          <button
            type="button"
            className="mobile-nav-close"
            aria-label="Cerrar menú"
            onClick={() => setMobileNavOpen(false)}
          >
            <i className="bi bi-x-lg" aria-hidden="true"></i>
          </button>
          <a href="#menu" onClick={() => setMobileNavOpen(false)}>Menú</a>
          {reservasActivas && (
            <a
              href="#reserva"
              onClick={(event) => {
                event.preventDefault();
                abrirModalAccion("reserva");
              }}
            >
              Reservas
            </a>
          )}
          <a href="#nosotros" onClick={() => setMobileNavOpen(false)}>Contacto</a>
        </nav>

        {mobileNavOpen && (
          <button
            type="button"
            className="mobile-nav-backdrop"
            aria-label="Cerrar menú"
            onClick={() => setMobileNavOpen(false)}
          ></button>
        )}

        <div className="header-actions">
          <div className="header-social" aria-label="Redes sociales">
            <span>Síguenos</span>
            {restaurante?.facebook && (
              <a href={restaurante.facebook} target="_blank" rel="noreferrer" aria-label="Facebook">
                <i className="bi bi-facebook" aria-hidden="true"></i>
              </a>
            )}
            {restaurante?.instagram && (
              <a href={restaurante.instagram} target="_blank" rel="noreferrer" aria-label="Instagram">
                <i className="bi bi-instagram" aria-hidden="true"></i>
              </a>
            )}
            {restaurante?.whatsapp && (
              <a
                href={`https://wa.me/${String(restaurante.whatsapp).replace(/\D/g, "")}`}
                target="_blank"
                rel="noreferrer"
                aria-label="WhatsApp"
              >
                <i className="bi bi-whatsapp" aria-hidden="true"></i>
              </a>
            )}
          </div>
          {carritoWhatsappActivo && !mostrarCarritoFlotante && renderBotonCarrito("cart-trigger-header")}
        </div>
      </header>

      <main className="page-content">
        <section className="hero-panel" id="inicio">
          <figure className="hero-visual hero-visual-left" aria-hidden="true">
            <img src={imagenPrincipalOptimizada} alt="" />
          </figure>

          <div className="hero-copy">
            {logoOptimizado && (
              <img
                className="hero-center-logo"
                src={logoOptimizado}
                alt={restaurante?.nombre_empresa}
                width="180"
                height="180"
              />
            )}
            <h1>{restaurante?.nombre_empresa}</h1>
            <p>
              {restaurante?.mensaje_bienvenida ||
                restaurante?.descripcion ||
                "Sabores preparados con ingredientes frescos para convertir cada momento en algo especial."}
            </p>

            <div className="hero-actions">
              {reservasActivas && (
                <a
                  className="button-primary"
                  href="#reserva"
                  onClick={(event) => {
                    event.preventDefault();
                    abrirModalAccion("reserva");
                  }}
                >
                  Reserva ahora
                </a>
              )}
              <a className="button-secondary" href="#menu">
                Ver menú
              </a>
              {carritoWhatsappActivo && (
                <button
                  type="button"
                  className="button-secondary hero-order-button"
                  onClick={() => setCarritoAbierto(true)}
                >
                  <i className="bi bi-basket2-fill" aria-hidden="true"></i>
                  Pedir ahora
                </button>
              )}
            </div>

            <div className="hero-tags" aria-label="Beneficios">
              <div className="hero-tags-track">
                <div className="hero-tags-group">
                  <span>Atención rápida</span>
                  <span>Ingredientes frescos</span>
                  <span>Preparado al momento</span>
                  <span>Sabor casero</span>
                  {carritoWhatsappActivo && <span>Delivery</span>}
                </div>
                <div className="hero-tags-group" aria-hidden="true">
                  <span>Atención rápida</span>
                  <span>Ingredientes frescos</span>
                  <span>Preparado al momento</span>
                  <span>Sabor casero</span>
                  {carritoWhatsappActivo && <span>Delivery</span>}
                </div>
              </div>
            </div>

            {restaurante?.link_delivery && (
              <div className="partner-row">
                <span>Pídelo por</span>

                <a
                  href={restaurante.link_delivery}
                  target="_blank"
                  rel="noreferrer"
                  className="partner-pill pedidosya-pill"
                >
                  <svg
                    width="22"
                    height="22"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M7 8V6.5C7 3.9 9.1 2 12 2s5 1.9 5 4.5V8"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                    <path
                      d="M5 8h14l-1 13H6L5 8Z"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M13 10l-4 5h3l-1 4 4-5h-3l1-4Z"
                      fill="currentColor"
                    />
                  </svg>

                  PedidosYa
                </a>
              </div>
            )}
          </div>

          <figure className="hero-visual hero-visual-right" aria-hidden="true">
            <img
              src={imagenesRestaurante[0]?.url || imagenFormularioOptimizada}
              alt=""
            />
          </figure>
        </section>

        <section className="promo-panel" id="promociones">
          <article className="promo-card promo-card-small commercial-showcase-card">
            <div className="promo-card-header">
              <span className="promo-tag">
                <GiFireBowl />
                Destacados y promociones
              </span>
              {destacadosConCarrusel && (
                <div className="featured-controls" aria-label="Controles de destacados">
                  <button
                    type="button"
                    aria-label="Ver destacados anteriores"
                    onClick={() => moverDestacados(-1)}
                  >
                    <i className="bi bi-chevron-left" aria-hidden="true"></i>
                  </button>
                  <button
                    type="button"
                    aria-label="Ver más destacados"
                    onClick={() => moverDestacados(1)}
                  >
                    <i className="bi bi-chevron-right" aria-hidden="true"></i>
                  </button>
                </div>
              )}
            </div>

            {(promociones.length > 0 || productosDestacados.length > 0) ? (
              <div
                ref={destacadosCarouselRef}
                className={`${destacadosClase} commercial-showcase`}
                aria-label="Carrusel de destacados y promociones"
                style={{
                  "--featured-visible": destacadosVisibles,
                }}
              >
                <div
                  className="featured-track"
                  style={{ transform: `translateX(-${destacadosOffset}px)` }}
                >
                  <div className="commercial-showcase-group">
                    {promociones.map((producto) => (
                      <div key={`promocion-${producto.id}`} className="featured-slide commercial-slide">
                        <div className="featured-slide-image">
                          <img
                            src={getProductImage(producto, { width: 520, height: 390 })}
                            alt={producto.nombre}
                            loading="lazy"
                            width="520"
                            height="390"
                          />
                        </div>

                        <span className="commercial-badge">Promoción</span>

                        <div className="promo-item-small">
                          <h3>{producto.nombre}</h3>
                          <strong>${Number(producto.precio).toLocaleString("es-CL")}</strong>
                          <button
                            type="button"
                            className="commercial-action"
                            onClick={() => handlePromotionClick(producto)}
                          >
                            Ver promoción
                          </button>
                        </div>
                      </div>
                    ))}

                    {productosDestacados.map((producto) => (
                      <div key={`destacado-${producto.id}`} className="featured-slide commercial-slide">
                        <div className="featured-slide-image">
                          <img
                            src={getProductImage(producto, { width: 420, height: 320 })}
                            alt={producto.nombre}
                            loading="lazy"
                            width="420"
                            height="320"
                          />
                        </div>

                        <span className="commercial-badge">Destacado</span>

                        <div className="promo-item-small">
                          <h3>{producto.nombre}</h3>
                          <strong>${Number(producto.precio).toLocaleString("es-CL")}</strong>
                          {carritoWhatsappActivo && (
                            <button
                              type="button"
                              className="commercial-action"
                              onClick={() => agregarAlCarrito(producto)}
                            >
                              Añadir
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="commercial-showcase-group" aria-hidden="true">
                    {promociones.map((producto) => (
                      <div key={`promocion-copy-${producto.id}`} className="featured-slide commercial-slide">
                        <div className="featured-slide-image">
                          <img
                            src={getProductImage(producto, { width: 520, height: 390 })}
                            alt=""
                            loading="lazy"
                            width="520"
                            height="390"
                          />
                        </div>
                        <span className="commercial-badge">Promoción</span>
                        <div className="promo-item-small">
                          <h3>{producto.nombre}</h3>
                          <strong>${Number(producto.precio).toLocaleString("es-CL")}</strong>
                        </div>
                      </div>
                    ))}

                    {productosDestacados.map((producto) => (
                      <div key={`destacado-copy-${producto.id}`} className="featured-slide commercial-slide">
                        <div className="featured-slide-image">
                          <img
                            src={getProductImage(producto, { width: 420, height: 320 })}
                            alt=""
                            loading="lazy"
                            width="420"
                            height="320"
                          />
                        </div>
                        <span className="commercial-badge">Destacado</span>
                        <div className="promo-item-small">
                          <h3>{producto.nombre}</h3>
                          <strong>${Number(producto.precio).toLocaleString("es-CL")}</strong>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p>No hay destacados ni promociones disponibles.</p>
            )}
          </article>
        </section>

        {selectedPromotion && (
          <div
            className="product-modal-backdrop"
            role="presentation"
            onClick={() => setSelectedPromotion(null)}
          >
            <article
              className="product-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="promotion-modal-title"
              onClick={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                className="product-modal-close"
                aria-label="Cerrar promoción"
                onClick={() => setSelectedPromotion(null)}
              >
                <i className="bi bi-x-lg" aria-hidden="true"></i>
              </button>

              <div className="product-modal-image">
                <img
                  src={getProductImage(selectedPromotion, { width: 900, height: 650 })}
                  alt={selectedPromotion.nombre}
                  loading="lazy"
                  width="900"
                  height="650"
                />
              </div>

              <div className="product-modal-content">
                <span className="product-modal-label">Promoción</span>
                <h2 id="promotion-modal-title">{selectedPromotion.nombre}</h2>
                <strong>${Number(selectedPromotion.precio).toLocaleString("es-CL")}</strong>
                <p>{selectedPromotion.descripcion || "Sin descripción disponible."}</p>
                {getProductConditions(selectedPromotion) && (
                  <p><small>{getProductConditions(selectedPromotion)}</small></p>
                )}
                {carritoWhatsappActivo && (
                  <div className="product-modal-cart-actions">
                    <label className="cart-modal-qty">
                      <span>Cantidad</span>
                      <input
                        type="number"
                        min="1"
                        max={MAX_UNIDADES_POR_PRODUCTO}
                        value={cantidadPromocion}
                        onChange={(event) => {
                          const value = Number(event.target.value);
                          setCantidadPromocion(
                            Math.min(
                              MAX_UNIDADES_POR_PRODUCTO,
                              Math.max(1, value || 1)
                            )
                          );
                        }}
                      />
                    </label>
                    <button
                      type="button"
                      className="producto-add-cart product-modal-add"
                      onClick={() => agregarAlCarrito(selectedPromotion, cantidadPromocion)}
                    >
                      Agregar al carrito
                    </button>
                  </div>
                )}
              </div>
            </article>
          </div>
        )}

        {carritoWhatsappActivo && (
          <section className="order-modes" aria-label="Pide como quieras">
            <div>
              <span>Pide como quieras</span>
              <h2>Elige tu forma favorita</h2>
            </div>
            <article>
              <i className="bi bi-whatsapp" aria-hidden="true"></i>
              <strong>Por WhatsApp</strong>
              <small>Rápido y directo</small>
            </article>
            <article>
              <i className="bi bi-truck" aria-hidden="true"></i>
              <strong>Delivery</strong>
              <small>Hasta tu puerta</small>
            </article>
            <article>
              <i className="bi bi-shop" aria-hidden="true"></i>
              <strong>Retiro en local</strong>
              <small>Pide y retira</small>
            </article>
            <article>
              <i className="bi bi-bag-check" aria-hidden="true"></i>
              <strong>Para llevar</strong>
              <small>Listo para salir</small>
            </article>
          </section>
        )}

        <section className="menu-wrapper" id="menu">
          <Menu
            categorias={categorias}
            onProductClick={handleClickProducto}
            fallbackImage={restaurante?.logo_url}
            carritoActivo={carritoWhatsappActivo}
            onAddToCart={agregarAlCarrito}
            maxCantidad={MAX_UNIDADES_POR_PRODUCTO}
          />
        </section>

        <section className="reservation-showcase">
          <span id="reserva" className="landing-action-anchor" aria-hidden="true"></span>
          <span id="solicitudes-especiales" className="landing-action-anchor" aria-hidden="true"></span>

          <article
            className="reservation-card"
            style={{
              "--about-bg": `url(${
                imagenFormularioOptimizada
              })`,
            }}
          >
            <div className="reservation-card-copy">
              <h2>{restaurante?.nombre_empresa}</h2>
              <p>
                {restaurante?.descripcion ||
                  "Reserva tu momento perfecto o solicita preparaciones especiales para ti."}
              </p>
            </div>

            {(solicitudesEspecialesActivas || reservasActivas) && (
              <div className="action-cards" aria-label="Acciones del restaurante">
                {solicitudesEspecialesActivas && (
                  <button
                    type="button"
                    className="action-card"
                    onClick={() => abrirModalAccion("solicitud")}
                  >
                    <i className="bi bi-stars" aria-hidden="true"></i>
                    <strong>Pedido Especial</strong>
                  </button>
                )}

                {reservasActivas && (
                  <button
                    type="button"
                    className="action-card"
                    onClick={() => abrirModalAccion("reserva")}
                  >
                    <i className="bi bi-calendar2-check" aria-hidden="true"></i>
                    <strong>Solicitar Reserva</strong>
                  </button>
                )}
              </div>
            )}
          </article>

          <div className="restaurant-details-column">
            <section className="gallery-panel" aria-label="Galería del restaurante">
              <h2>Galería</h2>
              <div className="gallery-grid">
                {imagenesRestaurante.length > 0 ? (
                  <div className="gallery-track">
                    <div className="gallery-group">
                      {imagenesRestaurante.map((imagen, index) => (
                        <button
                          key={imagen.id || imagen.url || index}
                          type="button"
                          className="gallery-card"
                          onClick={() => setSelectedGalleryImage(imagen)}
                          aria-label={`Ampliar ${imagen.label || `imagen ${index + 1}`}`}
                        >
                          <img
                            src={getOptimizedImageUrl(imagen.url, {
                              baseUrl: CLOUDINARY_BASE,
                              width: 520,
                              height: 390,
                            })}
                            alt={imagen.label || `Imagen ${index + 1} de ${restaurante?.nombre_empresa || "restaurante"}`}
                            loading="lazy"
                            width="520"
                            height="390"
                          />
                        </button>
                      ))}
                    </div>

                    <div className="gallery-group" aria-hidden="true">
                      {imagenesRestaurante.map((imagen, index) => (
                        <button
                          key={`gallery-copy-${imagen.id || imagen.url || index}`}
                          type="button"
                          className="gallery-card"
                          tabIndex="-1"
                          onClick={() => setSelectedGalleryImage(imagen)}
                        >
                          <img
                            src={getOptimizedImageUrl(imagen.url, {
                              baseUrl: CLOUDINARY_BASE,
                              width: 520,
                              height: 390,
                            })}
                            alt=""
                            loading="lazy"
                            width="520"
                            height="390"
                          />
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="gallery-empty">No hay imágenes disponibles.</p>
                )}
              </div>
            </section>

            <section className="about-panel" id="nosotros">
              <div className="about-panel-heading">
                {logoOptimizado && (
                  <img
                    src={logoOptimizado}
                    alt={restaurante?.nombre_empresa}
                    loading="lazy"
                    width="110"
                    height="110"
                  />
                )}
                <div>
                  <h2>Sobre Nosotros</h2>
                  <p>
                    {restaurante?.sobre_nosotros ||
                      restaurante?.descripcion ||
                      "Sabores que convierten cualquier momento en algo especial."}
                  </p>
                </div>
              </div>

              <div className="about-panel-details">
                <article>
                  <h3>Horarios</h3>
                  <p>Consulta nuestros horarios de atención.</p>
                </article>
                <article>
                  <h3>Ubicación</h3>
                  <p>{restaurante?.direccion}, {restaurante?.ciudad}</p>
                  {restaurante?.google_maps && (
                    <a href={restaurante.google_maps} target="_blank" rel="noreferrer">
                      Ver mapa
                    </a>
                  )}
                </article>
                <article>
                  <h3>Contacto</h3>
                  <p>{restaurante?.telefono || restaurante?.whatsapp}</p>
                </article>
                <article>
                  <h3>Síguenos</h3>
                  <div className="social-links">
                    {restaurante?.facebook && (
                      <a href={restaurante.facebook} target="_blank" rel="noreferrer" aria-label="Facebook">
                        <i className="bi bi-facebook"></i>
                      </a>
                    )}
                    {restaurante?.instagram && (
                      <a href={restaurante.instagram} target="_blank" rel="noreferrer" aria-label="Instagram">
                        <i className="bi bi-instagram"></i>
                      </a>
                    )}
                    {restaurante?.whatsapp && (
                      <a
                        href={`https://wa.me/${String(restaurante.whatsapp).replace(/\D/g, "")}`}
                        target="_blank"
                        rel="noreferrer"
                        aria-label="WhatsApp"
                      >
                        <i className="bi bi-whatsapp"></i>
                      </a>
                    )}
                  </div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <footer className="landing-footer">
          <p>
            © 2026 {restaurante?.nombre_empresa} · Desarrollado con Menly
          </p>
        </footer>
      </main>
      {selectedGalleryImage && (
        <div
          className="gallery-lightbox-backdrop"
          role="presentation"
          onClick={() => setSelectedGalleryImage(null)}
        >
          <section
            className="gallery-lightbox"
            role="dialog"
            aria-modal="true"
            aria-label="Imagen ampliada de la galería"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="gallery-lightbox-close"
              aria-label="Cerrar imagen"
              onClick={() => setSelectedGalleryImage(null)}
            >
              <i className="bi bi-x-lg" aria-hidden="true"></i>
            </button>
            <img
              src={getOptimizedImageUrl(selectedGalleryImage.url, {
                baseUrl: CLOUDINARY_BASE,
                width: 1400,
                height: 1000,
              })}
              alt={selectedGalleryImage.label || `Imagen de ${restaurante?.nombre_empresa || "restaurante"}`}
            />
          </section>
        </div>
      )}
      {carritoWhatsappActivo && mostrarCarritoFlotante && renderBotonCarrito("cart-trigger-floating")}
      {toastCarrito && <div className="cart-toast">{toastCarrito}</div>}
      {modalActivo && (
        <div
          className="landing-modal-backdrop"
          role="presentation"
          onClick={() => setModalActivo(null)}
        >
          <section
            className="landing-modal"
            role="dialog"
            aria-modal="true"
            aria-label={modalActivo === "reserva" ? "Reserva tu mesa" : "Solicitudes especiales"}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="landing-modal-close"
              aria-label="Cerrar"
              onClick={() => setModalActivo(null)}
            >
              <i className="bi bi-x-lg" aria-hidden="true"></i>
            </button>

            {modalActivo === "reserva" && reservasActivas && (
              <ReservaForm
                onSubmit={handleReserva}
                enviando={enviando}
                mensaje={mensaje}
                error={error}
              />
            )}

            {modalActivo === "solicitud" && solicitudesEspecialesActivas && (
              <SolicitudEspecialForm
                restauranteId={restaurante?.id}
                onSubmit={handleSolicitudEspecial}
                enviando={solicitudEnviando}
                mensaje={solicitudMensaje}
                error={solicitudError}
              />
            )}
          </section>
        </div>
      )}
      {carritoWhatsappActivo && carritoAbierto && (
        <div
          className="cart-modal-backdrop"
          role="presentation"
          onClick={() => setCarritoAbierto(false)}
        >
          <section
            className="cart-whatsapp-panel cart-whatsapp-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="cart-modal-title"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="product-modal-close"
              aria-label="Cerrar carrito"
              onClick={() => setCarritoAbierto(false)}
            >
              <i className="bi bi-x-lg" aria-hidden="true"></i>
            </button>

            <div className="cart-whatsapp-header">
              <span>Pedido por WhatsApp</span>
              <h2 id="cart-modal-title">Tu carrito</h2>
              <p>Revisa tu pedido, completa tus datos y envíalo al restaurante.</p>
            </div>

            <div className="cart-whatsapp-body">
              <div className="cart-items">
                {carrito.length === 0 ? (
                  <p className="cart-empty">Tu carrito está vacío</p>
                ) : (
                  carrito.map((item) => (
                    <article key={item.producto_id} className="cart-item">
                      <div>
                        <h3>{item.nombre}</h3>
                        <p>${item.precio.toLocaleString("es-CL")} c/u</p>
                      </div>
                      <div className="cart-quantity">
                        <button
                          type="button"
                          aria-label={`Disminuir ${item.nombre}`}
                          onClick={() => cambiarCantidadCarrito(item.producto_id, -1)}
                        >
                          -
                        </button>
                        <span>{item.cantidad}</span>
                        <button
                          type="button"
                          aria-label={`Aumentar ${item.nombre}`}
                          onClick={() => {
                            if (item.cantidad >= MAX_UNIDADES_POR_PRODUCTO) {
                              mostrarToastCarrito("Máximo 5 unidades por producto");
                              return;
                            }
                            cambiarCantidadCarrito(item.producto_id, 1);
                          }}
                        >
                          +
                        </button>
                      </div>
                      <strong>${(item.precio * item.cantidad).toLocaleString("es-CL")}</strong>
                      <button
                        type="button"
                        className="cart-remove"
                        onClick={() => eliminarDelCarrito(item.producto_id)}
                      >
                        Eliminar
                      </button>
                    </article>
                  ))
                )}
              </div>

              <form className="cart-form" onSubmit={handlePedidoWhatsApp}>
                <label>
                  <span>Nombre</span>
                  <input name="nombre_cliente" type="text" autoComplete="name" required />
                </label>
                <label>
                  <span>Teléfono</span>
                  <input name="telefono_cliente" type="tel" autoComplete="tel" required />
                </label>
                <label>
                  <span>Tipo de entrega</span>
                  <select
                    name="tipo_entrega"
                    required
                    value={tipoEntregaPedido}
                    onChange={(e) => setTipoEntregaPedido(e.target.value)}
                  >
                    <option value="" disabled>Selecciona una opción</option>
                    <option value="delivery">Delivery</option>
                    <option value="retiro_local">Retiro en local</option>
                    <option value="para_llevar">Para llevar</option>
                  </select>
                </label>
                {tipoEntregaPedido === "delivery" && (
                  <label>
                    <span>Dirección de entrega</span>
                    <input
                      name="direccion_entrega"
                      type="text"
                      autoComplete="street-address"
                      required
                      placeholder="Ej: Av. Pedro Aguirre Cerda 1234"
                    />
                  </label>
                )}

                <div className="cart-total">
                  <span>Total</span>
                  <strong>${totalCarrito.toLocaleString("es-CL")}</strong>
                </div>

                {pedidoMensaje && <p className="form-success">{pedidoMensaje}</p>}
                {pedidoError && <p className="form-error">{pedidoError}</p>}

                <button
                  type="submit"
                  className="button-primary cart-submit"
                  disabled={pedidoEnviando || carrito.length === 0}
                >
                  {pedidoEnviando ? "Enviando pedido..." : "Enviar pedido por WhatsApp"}
                </button>
              </form>
            </div>
          </section>
        </div>
      )}
      <WhatsAppFloatingButton telefono={restaurante?.whatsapp || restaurante?.telefono} />
    </div>
  );
}
