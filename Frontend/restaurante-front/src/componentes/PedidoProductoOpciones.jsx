import { obtenerGruposSnapshot } from "../utils/pedidoPersonalizacion";
import "../styles/PedidoProductoOpciones.css";

const formatearMoneda = (valor) =>
  new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(Number(valor || 0));

export default function PedidoProductoOpciones({ snapshot, mostrarPrecios = true, compacta = false }) {
  const grupos = obtenerGruposSnapshot(snapshot).filter((grupo) => Array.isArray(grupo?.opciones) && grupo.opciones.length);
  if (!grupos.length) return null;

  return (
    <div className={`pedido-opciones-snapshot ${compacta ? "is-compact" : ""}`}>
      {grupos.map((grupo, indice) => (
        <div key={`${grupo.grupo_id ?? grupo.id ?? grupo.grupo_nombre}-${indice}`}>
          <strong>{grupo.grupo_nombre || grupo.nombre || "Opciones"}:</strong>
          <span>
            {grupo.opciones.map((opcion, opcionIndice) => (
              <span key={`${opcion.opcion_id ?? opcion.id ?? opcion.nombre}-${opcionIndice}`}>
                {opcion.nombre || "Opcion"}
                {mostrarPrecios && Number(opcion.precio_adicional || 0) > 0
                  ? ` (+${formatearMoneda(opcion.precio_adicional)})`
                  : ""}
              </span>
            ))}
          </span>
        </div>
      ))}
    </div>
  );
}

