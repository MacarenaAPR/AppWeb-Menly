import { calcularPrecioOfertaVisual, formatearPrecioClp } from "../utils/precios";

export default function OfertaProductoControl({ form, setForm }) {
  const precioOferta = form.en_oferta
    ? calcularPrecioOfertaVisual(form.precio, form.porcentaje_descuento)
    : null;

  const actualizarOferta = (event) => {
    const activa = event.target.checked;
    setForm((actual) => ({
      ...actual,
      en_oferta: activa,
      porcentaje_descuento: activa ? actual.porcentaje_descuento : "",
    }));
  };

  const actualizarPorcentaje = (event) => {
    setForm((actual) => ({
      ...actual,
      porcentaje_descuento: event.target.value,
    }));
  };

  return (
    <div className="col-12 product-offer-config">
      <div className="product-offer-toggle-row">
        <div className="div-text-configuracion-producto product-offer-copy">
          <label className="form-label d-block mb-1" htmlFor="producto-en-oferta">
            Producto en oferta
          </label>
          <small>Activa un descuento temporal para este producto.</small>
        </div>
        <div className="form-check form-switch product-offer-switch">
          <input
            id="producto-en-oferta"
            className="form-check-input"
            type="checkbox"
            role="switch"
            name="en_oferta"
            checked={form.en_oferta}
            onChange={actualizarOferta}
          />
        </div>
      </div>

      {form.en_oferta && (
        <div className="product-offer-details">
          <div className="product-offer-fields">
            <label className="form-label" htmlFor="porcentaje-descuento">
              Porcentaje de descuento
            </label>
            <div className="input-group product-discount-input">
              <input
                id="porcentaje-descuento"
                className="form-control"
                type="number"
                inputMode="numeric"
                min="1"
                max="99"
                step="1"
                name="porcentaje_descuento"
                value={form.porcentaje_descuento}
                onChange={actualizarPorcentaje}
                required
              />
              <span className="input-group-text">%</span>
            </div>
          </div>

          {precioOferta !== null && (
            <div className="form-control product-offer-preview" aria-live="polite">
              <span className="product-offer-preview-item">
                <small>Precio normal</small>
                <strong className="product-offer-preview-original">
                  {formatearPrecioClp(form.precio)}
                </strong>
              </span>
              <span className="product-offer-preview-item">
                <small>Descuento</small>
                <strong className="product-offer-preview-discount">
                  {form.porcentaje_descuento}%
                </strong>
              </span>
              <span className="product-offer-preview-item">
                <small>Precio oferta</small>
                <strong className="product-offer-preview-effective">
                  {formatearPrecioClp(precioOferta)}
                </strong>
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
