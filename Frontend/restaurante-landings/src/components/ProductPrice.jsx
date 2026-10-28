import { estaEnOferta } from "../utils/pricing";

export default function ProductPrice({
  producto,
  precioOriginal,
  precioEfectivo,
  desde = false,
  className = "",
  as: Component = "span",
}) {
  const originalNumero = Number(precioOriginal);
  const efectivoNumero = Number(precioEfectivo);
  const original = Number.isFinite(originalNumero) ? originalNumero : 0;
  const efectivo = Number.isFinite(efectivoNumero) ? efectivoNumero : original;
  const enOferta = estaEnOferta(producto) && efectivo < original;
  const renderPrecio = (valor) => (
    <>
      {desde && <small className="product-price-prefix">Desde</small>}
      ${valor.toLocaleString("es-CL")}
    </>
  );

  if (!enOferta) {
    return (
      <Component className={`product-price ${className}`.trim()}>
        {renderPrecio(efectivo)}
      </Component>
    );
  }

  return (
    <Component className={`product-price product-price-with-offer ${className}`.trim()}>
      <span className="product-price-original">
        {renderPrecio(original)}
      </span>
      <span className="product-price-effective product-price-offer">
        {renderPrecio(efectivo)}
      </span>
      <span className="product-discount-badge">-{producto.porcentaje_descuento}%</span>
    </Component>
  );
}
