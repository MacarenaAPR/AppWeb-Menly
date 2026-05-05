import { useEffect, useState } from "react";

const CLOUDINARY_BASE = "https://res.cloudinary.com/dyo9thk2g/";

const renderCategoryIcon = (categoria) => (
  <i className={categoria?.icono || "fa-solid fa-utensils"} aria-hidden="true"></i>
);

const getProductImage = (producto, fallbackImage) => {
  const image =
    producto?.imagen_url ||
    producto?.imagen ||
    producto?.foto_url ||
    producto?.foto;

  if (!image) return fallbackImage || "/favicon.svg";
  if (String(image).startsWith("http") || String(image).startsWith("/")) return image;

  return CLOUDINARY_BASE + image;
};

export default function Menu({ categorias, onProductClick, fallbackImage }) {
  const [openCategory, setOpenCategory] = useState(0);
  const [selectedProduct, setSelectedProduct] = useState(null);

  useEffect(() => {
    if (categorias?.length && openCategory >= categorias.length) {
      setOpenCategory(0);
    }
  }, [categorias, openCategory]);

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
    setSelectedProduct(producto);
  };

  if (!categorias || categorias.length === 0) {
    return <p className="menu-loading">Cargando menú...</p>;
  }

  const selectedCategory = openCategory === null ? null : categorias[openCategory];

  return (
    <section className="menu-section">
      <div className="menu-header">
        <h2>Nuestro menú</h2>
        <p>Explora nuestras categorías y selecciona tus platos favoritos.</p>
      </div>

      <div className="menu-tabs" role="tablist" aria-label="Categorías del menú">
        {categorias.map((cat, index) => {
          const isOpen = openCategory === index;
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
          id={`menu-panel-${openCategory}`}
          role="tabpanel"
        >
          <div className="menu-bubble-header">
            <div className="category-title">
              <span className="category-icon">{renderCategoryIcon(selectedCategory)}</span>
              <span>{selectedCategory.categoria || selectedCategory.nombre}</span>
            </div>
            <span>{selectedCategory.productos?.length || 0} productos</span>
          </div>

          <div className="productos-list">
            {(selectedCategory.productos || []).map((producto) => (
              <button
                key={producto.id}
                type="button"
                className="producto-card"
                onClick={() => handleProductClick(producto)}
              >
                <div className="producto-head">
                  <h3>{producto.nombre}</h3>
                  <span>${Number(producto.precio).toLocaleString("es-CL")}</span>
                </div>
                <p>{producto.descripcion}</p>
              </button>
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
              <img src={getProductImage(selectedProduct, fallbackImage)} alt={selectedProduct.nombre} />
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
            </div>
          </article>
        </div>
      )}
    </section>
  );
}
