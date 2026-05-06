import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import Menu from "../components/Menu";
import ReservaForm from "../components/ReservaForm";
import WhatsAppFloatingButton from "../components/WhatsAppFloatingButton";
import { getOptimizedImageUrl } from "../utils/images";
import "../themes/themes.css";
import "../assets/FormHardcoreTheme-9.jpg";

const BASE_URL = import.meta.env.VITE_API_URL;

const CLOUDINARY_BASE = import.meta.env.VITE_CLOUDINARY_BASE;

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

export default function Home() {
  
  const { slug } = useParams();
  
  const [restaurante, setRestaurante] = useState(null);
  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPromotion, setSelectedPromotion] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [restauranteInactivo, setRestauranteInactivo] = useState(null);
  const promocionesCarouselRef = useRef(null);
  const destacadosCarouselRef = useRef(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [resRestaurante, resMenu] = await Promise.all([
          fetch(`${BASE_URL}/restaurantes/${slug}/`),
          fetch(`${BASE_URL}/menu/${slug}/`),
        ]);

        const dataRestaurante = await resRestaurante.json();
        const dataMenu = await resMenu.json();

        if (
          (resRestaurante.status === 403 && dataRestaurante?.estado === "inactivo") ||
          (resMenu.status === 403 && dataMenu?.estado === "inactivo")
        ) {
          setRestauranteInactivo(dataRestaurante?.estado === "inactivo" ? dataRestaurante : dataMenu);
          return;
        }

        setRestaurante(dataRestaurante);
        setCategorias(dataMenu);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [slug]);

  const handleClickProducto = async (id) => {
    try {
      await fetch(`${BASE_URL}/productos/${id}/click/`, {
        method: "POST",
      });
    } catch (error) {
      console.error("Error click", error);
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
    setSelectedPromotion(producto);
  };

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
      const res = await fetch(`${BASE_URL}/reservas/${slug}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });

      const result = await res.json();

      if (!res.ok) {
        setError(result.error || "No se pudo enviar la reserva. Intenta nuevamente.");
        return;
      }

      setMensaje("Reserva enviada correctamente. Te contactaremos para confirmar.");
      form.reset();
    } catch {
      setError("No se pudo enviar la reserva. Intenta nuevamente.");
    } finally {
      setEnviando(false);
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

    const destacadosTimer =
      productosDestacados.length > 1
        ? startAutoScroll(destacadosCarouselRef.current, 8000)
        : null;

    return () => {
      if (promocionesTimer) clearInterval(promocionesTimer);
      if (destacadosTimer) clearInterval(destacadosTimer);
    };
  }, [promociones.length, productosDestacados.length]);

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

  if (loading) {
    return (
      <div className="page-shell loading-screen">
        <p>Cargando menú...</p>
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

  return (
    <div
      className={`page-shell ${themeClass}`}
      style={{
        "--bg-principal": restaurante?.imgen_principal
          ? `url(${imagenPrincipalOptimizada})`
          : "none",
      }}
    >
      <header className="site-header">
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

        <nav className="site-nav">
          <a href="#inicio">Inicio</a>
          <a href="#menu">Menú</a>
          <a href="#promociones">Promociones</a>
          <a href="#nosotros">Nosotros</a>
          <a href="#reserva">Reserva</a>
        </nav>

        <a className="button-primary" href="#reserva">
          Escríbenos
        </a>
      </header>

      <main className="page-content">
        <section className="hero-panel" id="inicio">
          <div className="hero-copy">
            <span className="eyebrow">{restaurante?.nombre_empresa}</span>
            <h1>{restaurante?.mensaje_bienvenida}</h1>
            <p>
              {restaurante?.descripcion || "Platos preparados con ingredientes frescos, recetas caseras y mucho amor. Un estilo rústico y elegante para disfrutar desde la primera mordida."}
            </p>

            <div className="hero-actions">
              <a className="button-primary" href="#menu">
                Ver menú
              </a>
              <a className="button-secondary" href="#reserva">
                Reservar mesa
              </a>
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
        </section>

        <section className="promo-panel" id="promociones">
          <article className="promo-card promo-card-large">
            <div className="promo-card-header">
              <span className="promo-label">Promociones</span>
            </div>

            {promociones.length > 0 ? (
              <div
                ref={promocionesCarouselRef}
                className="promo-carousel"
                aria-label="Carrusel de promociones"
              >
                {promociones.map((producto) => (
                  <div key={producto.id} className="promo-slide">
                    <div className="promo-slide-image">
                      <img
                        src={getProductImage(producto, { width: 720, height: 460 })}
                        alt={producto.nombre}
                        loading="lazy"
                        width="720"
                        height="460"
                      />
                    </div>

                    <div className="promo-slide-content">
                      <div className="promo-item">
                        <h2>{producto.nombre}</h2>
                        <p>{producto.descripcion}</p>
                        <strong>${Number(producto.precio).toLocaleString("es-CL")}</strong>
                      </div>

                      <button
                        type="button"
                        className="promo-button"
                        onClick={() => handlePromotionClick(producto)}
                      >
                        Ver promoción
                      </button>
                    </div>

                    {getProductConditions(producto) && (
                      <p className="promo-conditions">
                        <small>{getProductConditions(producto)}</small>
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p>No hay promociones disponibles.</p>
            )}
          </article>

          <article className="promo-card promo-card-small">
            <div className="promo-card-header">
              <span className="promo-tag">Destacados</span>
            </div>

            {productosDestacados.length > 0 ? (
              <div
                ref={destacadosCarouselRef}
                className="featured-carousel"
                aria-label="Carrusel de productos destacados"
              >
                {productosDestacados.map((producto) => (
                  <div key={producto.id} className="featured-slide">
                    <div className="featured-slide-image">
                      <img
                        src={getProductImage(producto, { width: 420, height: 320 })}
                        alt={producto.nombre}
                        loading="lazy"
                        width="420"
                        height="320"
                      />
                    </div>

                    <div className="promo-item-small">
                      <p>{producto.categoriaNombre}</p>
                      <h3>{producto.nombre}</h3>
                      <strong>${Number(producto.precio).toLocaleString("es-CL")}</strong>
                    </div>
                  </div>
                ))
                }
              </div>
            ) : (
              <p>No hay productos destacados.</p>
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
              </div>
            </article>
          </div>
        )}

        <section
          className="highlights-grid"
          id="nosotros"
          style={{
            "--about-bg": `url(${
              imagenFormularioOptimizada
            })`,
          }}
        >
          <article className="about-card">
            <h2>Sobre nosotros</h2>
            <p>
              {restaurante?.sobre_nosotros || "Somos apasionados por la buena comida. Combinamos recetas tradicionales con ingredientes frescos para ofrecerte una experiencia única."}
            </p>
            <a className="link-button" href="#reserva">
              Conócenos más
            </a>
          </article>

          <div className="info-grid">
            <article className="info-box">

              <div>
              <h3>Ubicación</h3>
              <p>{restaurante?.direccion}, {restaurante?.ciudad}</p>
              {restaurante?.google_maps && (
                <a href={restaurante?.google_maps} target="_blank" rel="noreferrer">
                  Ver en Google Maps
                </a>
              )}
              </div>
            </article>
            <article className="info-box">
              <div>
              <h3>Contacto</h3>
              <p>Teléfono: {restaurante?.telefono}</p>
              {restaurante?.whatsapp && (
                <p>WhatsApp: {restaurante?.whatsapp}</p>
              )}
              </div>
            </article>
            <article className="info-box">
              <div>
              <h3>Síguenos</h3>
              <div className="social-links">
                {restaurante?.instagram && (
                  <a href={restaurante?.instagram} target="_blank" rel="noreferrer" title="Instagram">
                    <i className="bi bi-instagram"></i>
                  </a>
                )}
                {restaurante?.facebook && (
                  <a href={restaurante?.facebook} target="_blank" rel="noreferrer" title="Facebook">
                    <i className="bi bi-facebook"></i>
                  </a>
                )}

              </div>
              </div>
            </article>
          </div>
        </section>

        <section className="menu-wrapper" id="menu">
          <Menu
            categorias={categorias}
            onProductClick={handleClickProducto}
            fallbackImage={restaurante?.logo_url}
          />
        </section>

        <section className="reserve-wrapper" id="reserva">
          <ReservaForm
            onSubmit={handleReserva}
            enviando={enviando}
            mensaje={mensaje}
            error={error}
          />
        </section>

        <section className="gallery-panel" aria-label="Un vistazo a nuestro espacio">
          <h2>Un vistazo a nuestro espacio</h2>
          <div className="gallery-grid">
            {imagenesRestaurante.length > 0 ? (
              imagenesRestaurante.map((imagen, index) => (
                <figure key={imagen.id || imagen.url || index} className="gallery-card">
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
                  
                </figure>
              ))
            ) : (
              <p className="gallery-empty">No hay imágenes disponibles.</p>
            )}
          </div>
        </section>
      </main>
      <WhatsAppFloatingButton telefono={restaurante?.whatsapp || restaurante?.telefono} />
    </div>
  );
}
