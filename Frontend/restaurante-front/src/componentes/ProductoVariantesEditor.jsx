const nuevaVariante = (orden = 0) => ({
  nombre: "",
  descripcion: "",
  precio: "",
  activo: true,
  orden,
});

export default function ProductoVariantesEditor({ variantes, onChange }) {
  const actualizar = (index, campo, valor) => {
    onChange(variantes.map((variante, i) => (
      i === index ? { ...variante, [campo]: valor } : variante
    )));
  };

  const eliminar = (index) => {
    onChange(variantes.filter((_, i) => i !== index));
  };

  return (
    <div className="form mt-4 variantes-editor">
      <div className="variantes-editor-header">
        <div>
          <p className="info-header">
            <span><i className="bi bi-layers"></i></span>{" "}
            Variantes o tamaños
          </p>
          <small>Opcional. Ejemplos: Individual, Mediana o Familiar.</small>
        </div>
        <button
          type="button"
          className="btn btn-outline-primary"
          onClick={() => onChange([...variantes, nuevaVariante(variantes.length)])}
        >
          <i className="bi bi-plus-lg"></i> Agregar variante
        </button>
      </div>

      {variantes.length === 0 ? (
        <p className="variantes-empty">Este producto usará su precio actual.</p>
      ) : variantes.map((variante, index) => (
        <div className="variante-row" key={variante.id || `nueva-${index}`}>
          <div className="row g-3">
            <div className="col-md-4">
              <label className="form-label">Nombre <span className="text-danger">*</span></label>
              <input
                className="form-control"
                value={variante.nombre}
                placeholder="Ej: Familiar"
                onChange={(e) => actualizar(index, "nombre", e.target.value)}
                required
              />
            </div>
            <div className="col-md-4">
              <label className="form-label">Precio (CLP) <span className="text-danger">*</span></label>
              <input
                className="form-control"
                type="number"
                min="0"
                value={variante.precio}
                placeholder="Ej: 18000"
                onChange={(e) => actualizar(index, "precio", e.target.value)}
                required
              />
            </div>
            <div className="col-md-2">
              <label className="form-label">Orden</label>
              <input
                className="form-control"
                type="number"
                min="0"
                value={variante.orden}
                onChange={(e) => actualizar(index, "orden", e.target.value)}
              />
            </div>
            <div className="col-md-2 variante-active-field">
              <label className="form-label">Activo</label>
              <input
                className="form-check-input"
                type="checkbox"
                checked={variante.activo}
                onChange={(e) => actualizar(index, "activo", e.target.checked)}
              />
            </div>
            <div className="col-12">
              <label className="form-label">Descripción</label>
              <input
                className="form-control"
                value={variante.descripcion}
                placeholder="Ej: Ideal para 3 o 4 personas"
                onChange={(e) => actualizar(index, "descripcion", e.target.value)}
              />
            </div>
          </div>
          <button type="button" className="btn btn-outline-danger variante-remove" onClick={() => eliminar(index)}>
            <i className="bi bi-trash3"></i> Eliminar
          </button>
        </div>
      ))}
    </div>
  );
}
