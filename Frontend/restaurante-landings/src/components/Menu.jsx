import { useEffect, useRef, useState } from "react";
import { getOptimizedImageUrl } from "../utils/images";
import { MAX_CANTIDAD_POR_PRODUCTO } from "../constants/carrito";

const CLOUDINARY_BASE = import.meta.env.VITE_CLOUDINARY_BASE;

const renderCategoryIcon = (categoria) => (
  <i className={categoria?.icono || "fa-solid fa-utensils"} aria-hidden="true"></i>
);

const getProductImage = (producto, fallbackImage, size = {}) => {
  const image =
    producto?.imagen_url ||
    producto?.imagen ||
    producto?.foto_url ||
    producto?.foto;

  return getOptimizedImageUrl(image, {
    baseUrl: CLOUDINARY_BASE,
    fallbackImage,
    width: size.width || 900,
    height: size.height || 650,
  });
};

const variantesActivas = (producto) => (producto?.variantes || []).filter((variante) => variante.activo !== false);
const precioMinimo = (producto) => {
  const variantes = variantesActivas(producto);
  return variantes.length ? Math.min(...variantes.map((variante) => Number(variante.precio))) : Number(producto.precio);
};

export default function Menu({
  categorias,
  onProductClick,
  fallbackImage,
  carritoActivo = false,
  onAddToCart,
  maxCantidad = MAX_CANTIDAD_POR_PRODUCTO,
  onMaxCantidad,
  carritoMensajeInactivo = "",
}) {
  const menuTabsRef = useRef(null);
  const dragStateRef = useRef({
    isDragging: false,
    startX: 0,
    startScrollLeft: 0,
    hasMoved: false,
  });
  const suppressClickRef = useRef(false);
  const suppressClickTimerRef = useRef(null);
  const [openCategory, setOpenCategory] = useState(0);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [cantidadProducto, setCantidadProducto] = useState(1);
  const [varianteSeleccionadaId, setVarianteSeleccionadaId] = useState("");
  const [cantidadesProductos, setCantidadesProductos] = useState({});

  useEffect(
    () => () => {
      window.clearTimeout(suppressClickTimerRef.current);
    },
    []
  );

  useEffect(() => {
    if (!selectedProduct) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setSelectedProduct(null);
      }
    };

    document.body.classList.add("modal-open");
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.classList.remove("modal-open");
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [selectedProduct]);

  const handleProductClick = (producto) => {
    onProductClick(producto.id);
    setCantidadProducto(1);
    const variantes = variantesActivas(producto);
    setVarianteSeleccionadaId(variantes.length === 1 ? String(variantes[0].id) : "");
    setSelectedProduct(producto);
  };

  const agregarDesdeTarjeta = (producto) => {
    if (variantesActivas(producto).length) {
      handleProductClick(producto);
      return;
    }
    onAddToCart?.(producto, getCantidadProductoCard(producto.id), null);
  };

  const getCantidadProductoCard = (productoId) =>
    cantidadesProductos[productoId] || 1;

  const cambiarCantidadProductoCard = (productoId, delta) => {
    const cantidadActual = getCantidadProductoCard(productoId);
    if (delta > 0 && cantidadActual >= maxCantidad) {
      onMaxCantidad?.();
      return;
    }

    setCantidadesProductos((cantidadesActuales) => {
      const cantidadVigente = cantidadesActuales[productoId] || 1;
      const nuevaCantidad = Math.min(
        maxCantidad,
        Math.max(1, cantidadVigente + delta)
      );

      return {
        ...cantidadesActuales,
        [productoId]: nuevaCantidad,
      };
    });
  };

  const handleTabsMouseDown = (event) => {
    if (event.button !== 0) return;

    const container = menuTabsRef.current;
    if (!container) return;

    window.clearTimeout(suppressClickTimerRef.current);
    suppressClickRef.current = false;
    dragStateRef.current = {
      isDragging: true,
      startX: event.clientX,
      startScrollLeft: container.scrollLeft,
      hasMoved: false,
    };
  };

  const handleTabsMouseMove = (event) => {
    const container = menuTabsRef.current;
    const dragState = dragStateRef.current;

    if (!container || !dragState.isDragging) return;

    const distance = event.clientX - dragState.startX;

    if (!dragState.hasMoved && Math.abs(distance) > 4) {
      dragState.hasMoved = true;
      suppressClickRef.current = true;
      container.classList.add("is-dragging");
    }

    if (!dragState.hasMoved) return;

    event.preventDefault();
    container.scrollLeft = dragState.startScrollLeft - distance;
  };

  const stopTabsDrag = () => {
    const container = menuTabsRef.current;
    const didMove = dragStateRef.current.hasMoved;

    dragStateRef.current.isDragging = false;
    dragStateRef.current.hasMoved = false;
    container?.classList.remove("is-dragging");

    if (didMove) {
      suppressClickTimerRef.current = window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
    }
  };

  const handleCategoryClick = (index, isOpen) => {
    if (suppressClickRef.current) return;
    setOpenCategory(isOpen ? null : index);
  };

  const handleCategoryFocus = (event) => {
    event.currentTarget.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "nearest",
    });
  };

  if (!categorias || categorias.length === 0) {
    return <p className="menu-loading">Cargando menú...</p>;
  }

  const activeCategory =
    openCategory === null || openCategory < categorias.length ? openCategory : 0;
  const selectedCategory = activeCategory === null ? null : categorias[activeCategory];
  const selectedCategoryName =
    selectedCategory?.categoria || selectedCategory?.nombre || "Categoría";

  return (
    <section className="menu-section">
      <div className="menu-header">
        <h2>Menú</h2>
        <p>Explora nuestras categorías y selecciona tus platos favoritos.</p>
        {carritoMensajeInactivo && (
          <span className="menu-order-disabled-message">
            {carritoMensajeInactivo}
          </span>
        )}
      </div>

      <div
        ref={menuTabsRef}
        className="menu-tabs"
        role="tablist"
        aria-label="Categorías del menú"
        onMouseDown={handleTabsMouseDown}
        onMouseMove={handleTabsMouseMove}
        onMouseUp={stopTabsDrag}
        onMouseLeave={stopTabsDrag}
      >
        {categorias.map((cat, index) => {
          const isOpen = activeCategory === index;
          const categoryName = cat.categoria || cat.nombre || `Categoría ${index + 1}`;

          return (
            <button
              key={cat.id || categoryName || index}
              type="button"
              className={`menu-tab ${isOpen ? "is-active" : ""}`}
              aria-selected={isOpen}
              aria-expanded={isOpen}
              aria-controls={`menu-panel-${index}`}
              role="tab"
              onClick={() => handleCategoryClick(index, isOpen)}
              onFocus={handleCategoryFocus}
            >
              <span className="category-icon">{renderCategoryIcon(cat)}</span>
              <span>{categoryName}</span>
            </button>
          );
        })}
      </div>

      {selectedCategory && (
        <div
          className="menu-bubble"
          id={`menu-panel-${activeCategory}`}
          role="tabpanel"
        >
          <div className="menu-bubble-header">
            <div className="category-title">
              <span className="category-icon">{renderCategoryIcon(selectedCategory)}</span>
              <span>{selectedCategoryName}</span>
            </div>
            <span>{selectedCategory.productos?.length || 0} productos</span>
          </div>

          <div className="productos-list">
            {(selectedCategory.productos || []).map((producto) => (
              <article
                key={producto.id}
                className="producto-card"
              >
                <button
                  type="button"
                  className="producto-card-main"
                  onClick={() => handleProductClick(producto)}
                >
                  <div className="producto-card-image">
                    <img
                      src={getProductImage(producto, fallbackImage, { width: 220, height: 220 })}
                      alt={producto.nombre}
                      loading="lazy"
                      width="220"
                      height="220"
                    />
                  </div>

                  <div className="producto-card-content">
                    <div className="producto-head">
                      <div>
                        <h3>{producto.nombre}</h3>
                        <span className="producto-category">{selectedCategoryName}</span>
                      </div>
                      <span className="producto-card-price">
                        {variantesActivas(producto).length > 0 && <small>Desde</small>}
                        ${precioMinimo(producto).toLocaleString("es-CL")}
                      </span>
                    </div>
                    <p>{producto.descripcion}</p>
                    <span className="producto-action">Ver detalle</span>
                  </div>
                </button>
                {carritoActivo && (
                  <div className="producto-card-actions">
                    <div
                      className="producto-quantity-control"
                      aria-label={`Cantidad de ${producto.nombre}`}
                    >
                      <button
                        type="button"
                        className="producto-quantity-btn"
                        aria-label={`Disminuir cantidad de ${producto.nombre}`}
                        onClick={() => cambiarCantidadProductoCard(producto.id, -1)}
                        disabled={getCantidadProductoCard(producto.id) <= 1}
                      >
                        −
                      </button>
                      <span className="producto-quantity-value">
                        {getCantidadProductoCard(producto.id)}
                      </span>
                      <button
                        type="button"
                        className="producto-quantity-btn"
                        aria-label={`Aumentar cantidad de ${producto.nombre}`}
                        onClick={() => cambiarCantidadProductoCard(producto.id, 1)}
                      >
                        +
                      </button>
                    </div>

                    <button
                      type="button"
                      className="producto-add-cart"
                      onClick={() => agregarDesdeTarjeta(producto)}
                    >
                      Agregar
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        </div>
      )}

      {selectedProduct && (
        <div
          className="product-modal-backdrop"
          role="presentation"
          onClick={() => setSelectedProduct(null)}
        >
          <article
            className="product-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="product-modal-title"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="product-modal-close"
              aria-label="Cerrar producto"
              onClick={() => setSelectedProduct(null)}
            >
              <i className="bi bi-x-lg" aria-hidden="true"></i>
            </button>

            <div className="product-modal-image">
              <img
                src={getProductImage(selectedProduct, fallbackImage, { width: 900, height: 650 })}
                alt={selectedProduct.nombre}
                loading="lazy"
                width="900"
                height="650"
              />
            </div>

            <div className="product-modal-content">
              <h2 id="product-modal-title">{selectedProduct.nombre}</h2>
              {variantesActivas(selectedProduct).length === 0 && (
                <strong>${Number(selectedProduct.precio).toLocaleString("es-CL")}</strong>
              )}
              <p>{selectedProduct.descripcion || "Sin descripción disponible."}</p>
              {selectedProduct.condiciones && (
                <p className="promo-conditions">
                  <small>{selectedProduct.condiciones}</small>
                </p>
              )}
              {carritoActivo && (
                <div className="product-modal-cart-actions">
                  {variantesActivas(selectedProduct).length > 0 && (
                    <fieldset className="product-variants" aria-label="Selecciona un tamaño">
                      <legend>Selecciona un tamaño</legend>
                      {variantesActivas(selectedProduct).map((variante) => (
                        <label className="product-variant-option" key={variante.id}>
                          <input
                            type="radio"
                            name={`variante-${selectedProduct.id}`}
                            value={variante.id}
                            checked={String(varianteSeleccionadaId) === String(variante.id)}
                            onChange={() => setVarianteSeleccionadaId(String(variante.id))}
                          />
                          <span>
                            <strong>{variante.nombre}</strong>
                            {variante.descripcion && <small>{variante.descripcion}</small>}
                          </span>
                          <b>${Number(variante.precio).toLocaleString("es-CL")}</b>
                        </label>
                      ))}
                    </fieldset>
                  )}
                  <label className="cart-modal-qty">
                    <span>Cantidad</span>
                    <input
                      type="number"
                      min="1"
                      max={maxCantidad}
                      value={cantidadProducto}
                      onChange={(event) => {
                        const value = Number(event.target.value);
                        if (value > maxCantidad) {
                          onMaxCantidad?.();
                        }
                        setCantidadProducto(
                          Math.min(maxCantidad, Math.max(1, value || 1))
                        );
                      }}
                    />
                  </label>
                  <button
                    type="button"
                    className="producto-add-cart product-modal-add"
                    disabled={variantesActivas(selectedProduct).length > 0 && !varianteSeleccionadaId}
                    onClick={() => {
                      const variante = variantesActivas(selectedProduct).find(
                        (item) => String(item.id) === String(varianteSeleccionadaId)
                      );
                      onAddToCart?.(selectedProduct, cantidadProducto, variante || null);
                    }}
                  >
                    Agregar
                  </button>
                </div>
              )}
            </div>
          </article>
        </div>
      )}
    </section>
  );
}
