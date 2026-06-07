import { useEffect, useState } from "react";
import { getOptimizedImageUrl } from "../utils/images";

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

export default function Menu({
  categorias,
  onProductClick,
  fallbackImage,
  carritoActivo = false,
  onAddToCart,
  maxCantidad = 5,
}) {
  const [openCategory, setOpenCategory] = useState(0);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [cantidadProducto, setCantidadProducto] = useState(1);

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
    setSelectedProduct(producto);
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
        <h2>Nuestro menú</h2>
        <p>Explora nuestras categorías y selecciona tus platos favoritos.</p>
      </div>

      <div className="menu-tabs" role="tablist" aria-label="Categorías del menú">
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
              onClick={() => setOpenCategory(isOpen ? null : index)}
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
                      <span>${Number(producto.precio).toLocaleString("es-CL")}</span>
                    </div>
                    <p>{producto.descripcion}</p>
                    <span className="producto-action">Ver detalle</span>
                  </div>
                </button>
                {carritoActivo && (
                  <button
                    type="button"
                    className="producto-add-cart"
                    onClick={() => onAddToCart?.(producto)}
                  >
                    Agregar al carrito
                  </button>
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
              <strong>${Number(selectedProduct.precio).toLocaleString("es-CL")}</strong>
              <p>{selectedProduct.descripcion || "Sin descripción disponible."}</p>
              {selectedProduct.condiciones && (
                <p className="promo-conditions">
                  <small>{selectedProduct.condiciones}</small>
                </p>
              )}
              {carritoActivo && (
                <div className="product-modal-cart-actions">
                  <label className="cart-modal-qty">
                    <span>Cantidad</span>
                    <input
                      type="number"
                      min="1"
                      max={maxCantidad}
                      value={cantidadProducto}
                      onChange={(event) => {
                        const value = Number(event.target.value);
                        setCantidadProducto(
                          Math.min(maxCantidad, Math.max(1, value || 1))
                        );
                      }}
                    />
                  </label>
                  <button
                    type="button"
                    className="producto-add-cart product-modal-add"
                    onClick={() => onAddToCart?.(selectedProduct, cantidadProducto)}
                  >
                    Agregar al carrito
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
