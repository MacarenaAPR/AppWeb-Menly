import { useId } from "react";
import {
  cambiarOpcionSeleccionada,
  obtenerSeleccionGrupo,
  obtenerTextoSeleccion,
} from "../utils/productCustomization";

const formatearCLP = (valor) =>
  Number(valor || 0).toLocaleString("es-CL");

export default function ProductoOpcionesSelector({
  gruposOpciones = [],
  selecciones = {},
  errores = {},
  onChange,
}) {
  const selectorId = useId().replace(/:/g, "");

  if (!gruposOpciones.length) return null;

  return (
    <div className="product-customization" aria-label="Personaliza tu producto">
      <div className="product-customization-heading">
        <strong>Personalización</strong>
        <small>Configura el producto a tu gusto.</small>
      </div>

      {gruposOpciones.map((grupo) => {
        const seleccionadas = obtenerSeleccionGrupo(selecciones, grupo.id);
        const maximo = grupo.maximo_selecciones === null
          ? null
          : Number(grupo.maximo_selecciones);
        const seleccionUnica = maximo === 1;
        const permiteVacio =
          seleccionUnica &&
          grupo.obligatorio !== true &&
          Number(grupo.minimo_selecciones || 0) === 0;
        const maximoAlcanzado = maximo !== null && seleccionadas.length >= maximo;
        const error = errores[String(grupo.id)];

        return (
          <fieldset
            className={`product-option-group ${error ? "has-error" : ""}`}
            key={grupo.id}
            aria-describedby={error ? `${selectorId}-error-${grupo.id}` : undefined}
          >
            <legend>
              <span>{grupo.nombre}</span>
              <small>{obtenerTextoSeleccion(grupo)}</small>
            </legend>

            <div className="product-option-list">
              {permiteVacio && (
                <label
                  className={`product-option ${seleccionadas.length === 0 ? "is-selected" : ""}`}
                  htmlFor={`${selectorId}-grupo-${grupo.id}-sin-opcion`}
                >
                  <input
                    id={`${selectorId}-grupo-${grupo.id}-sin-opcion`}
                    type="radio"
                    name={`${selectorId}-grupo-${grupo.id}`}
                    checked={seleccionadas.length === 0}
                    onChange={() => onChange({ ...selecciones, [String(grupo.id)]: [] })}
                  />
                  <span className="product-option-name"><strong>Sin opción</strong></span>
                  <b>Incluida</b>
                </label>
              )}
              {(grupo.opciones || []).map((opcion) => {
                const opcionId = String(opcion.id);
                const seleccionada = seleccionadas.includes(opcionId);
                const noDisponible = opcion.disponible === false;
                const bloqueadaPorMaximo = !seleccionUnica && !seleccionada && maximoAlcanzado;
                const deshabilitada = noDisponible || bloqueadaPorMaximo;
                const inputId = `${selectorId}-grupo-${grupo.id}-opcion-${opcion.id}`;

                return (
                  <label
                    className={`product-option ${seleccionada ? "is-selected" : ""} ${deshabilitada ? "is-disabled" : ""}`}
                    htmlFor={inputId}
                    key={opcion.id}
                  >
                    <input
                      id={inputId}
                      type={seleccionUnica ? "radio" : "checkbox"}
                      name={`${selectorId}-grupo-${grupo.id}`}
                      checked={seleccionada}
                      disabled={deshabilitada}
                      onChange={() => onChange(cambiarOpcionSeleccionada(selecciones, grupo, opcion.id))}
                    />
                    <span className="product-option-name">
                      <strong>{opcion.nombre}</strong>
                      {noDisponible && <small>No disponible</small>}
                      {bloqueadaPorMaximo && <small>Máximo alcanzado</small>}
                    </span>
                    <b>
                      {Number(opcion.precio_adicional) > 0
                        ? `+$${formatearCLP(opcion.precio_adicional)}`
                        : "Incluida"}
                    </b>
                  </label>
                );
              })}
            </div>

            {error && (
              <p className="product-option-error" id={`${selectorId}-error-${grupo.id}`} role="alert">
                {error}
              </p>
            )}
          </fieldset>
        );
      })}
    </div>
  );
}
