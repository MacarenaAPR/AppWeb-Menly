import { useId } from "react";
import {
  cambiarOpcionSeleccionada,
  obtenerSeleccionGrupo,
  obtenerTextoSeleccion,
} from "../utils/pedidoPersonalizacion";

const formatearMoneda = (valor) => Number(valor || 0).toLocaleString("es-CL");

export default function ProductoOpcionesSelectorPos({ grupos = [], selecciones = {}, errores = {}, onChange }) {
  const idBase = useId().replace(/:/g, "");
  if (!grupos.length) return null;

  return (
    <div className="pedido-opciones-selector">
      {grupos.map((grupo) => {
        const seleccionadas = obtenerSeleccionGrupo(selecciones, grupo.id);
        const maximo = grupo.maximo_selecciones === null ? null : Number(grupo.maximo_selecciones);
        const unica = maximo === 1;
        const permiteVacio = unica && !grupo.obligatorio && Number(grupo.minimo_selecciones || 0) === 0;
        const maximoAlcanzado = maximo !== null && seleccionadas.length >= maximo;
        return (
          <fieldset key={grupo.id} className={errores[String(grupo.id)] ? "has-error" : ""}>
            <legend><strong>{grupo.nombre}</strong><small>{obtenerTextoSeleccion(grupo)}</small></legend>
            {permiteVacio && (
              <label>
                <input type="radio" name={`${idBase}-${grupo.id}`} checked={!seleccionadas.length} onChange={() => onChange({ ...selecciones, [String(grupo.id)]: [] })} />
                <span>Sin opcion</span><b>Incluida</b>
              </label>
            )}
            {(grupo.opciones || []).map((opcion) => {
              const seleccionada = seleccionadas.includes(String(opcion.id));
              const agotada = opcion.disponible === false;
              const bloqueada = !unica && !seleccionada && maximoAlcanzado;
              return (
                <label key={opcion.id} className={seleccionada ? "is-selected" : ""}>
                  <input
                    type={unica ? "radio" : "checkbox"}
                    name={`${idBase}-${grupo.id}`}
                    checked={seleccionada}
                    disabled={agotada || bloqueada}
                    onChange={() => onChange(cambiarOpcionSeleccionada(selecciones, grupo, opcion.id))}
                  />
                  <span>{opcion.nombre}<small>{agotada ? "No disponible" : bloqueada ? "Maximo alcanzado" : ""}</small></span>
                  <b>{Number(opcion.precio_adicional) > 0 ? `+$${formatearMoneda(opcion.precio_adicional)}` : "Incluida"}</b>
                </label>
              );
            })}
            {errores[String(grupo.id)] && <p role="alert">{errores[String(grupo.id)]}</p>}
          </fieldset>
        );
      })}
    </div>
  );
}
