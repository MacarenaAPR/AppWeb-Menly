const formatearMoneda = (valor) =>
  new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(Number(valor || 0));

export default function PedidoOpcionesSnapshot({ item }) {
  const grupos = item?.grupos_opciones || item?.opciones_snapshot || [];
  if (!grupos.some((grupo) => grupo?.opciones?.length)) return null;

  return (
    <div className="tracking-item-options">
      {grupos.filter((grupo) => grupo?.opciones?.length).map((grupo, index) => (
        <p key={`${grupo.grupo_id ?? grupo.grupo_nombre}-${index}`}>
          <strong>{grupo.grupo_nombre || grupo.nombre || "Opciones"}:</strong>{" "}
          {grupo.opciones.map((opcion) => (
            `${opcion.nombre}${Number(opcion.precio_adicional || 0) > 0 ? ` (+${formatearMoneda(opcion.precio_adicional)})` : ""}`
          )).join(", ")}
        </p>
      ))}
    </div>
  );
}
