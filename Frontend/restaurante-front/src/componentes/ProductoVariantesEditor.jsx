import { useEffect, useState } from "react";

const crearVariante = (orden = 0) => ({
  nombre: "",
  descripcion: "",
  precio: "",
  activo: true,
  orden,
});

const formatearCLP = (valor) => new Intl.NumberFormat("es-CL", {
  style: "currency",
  currency: "CLP",
  maximumFractionDigits: 0,
}).format(Number(valor) || 0);

function VarianteRow({ variante, onEdit, onDelete }) {
  return (
    <div className="variante-list-row" role="row">
      <div className="variante-list-name" role="cell" data-label="Variante">
        <strong>{variante.nombre}</strong>
        {variante.descripcion && <small>{variante.descripcion}</small>}
      </div>
      <span role="cell" data-label="Precio">{formatearCLP(variante.precio)}</span>
      <span role="cell" data-label="Estado">
        <span className={`variante-status ${variante.activo !== false ? "is-active" : "is-inactive"}`}>
          {variante.activo !== false ? "Activa" : "Inactiva"}
        </span>
      </span>
      <span role="cell" data-label="Orden">{Number(variante.orden) || 0}</span>
      <div className="variante-list-actions" role="cell" data-label="Acciones">
        <button type="button" className="variante-icon-button" onClick={onEdit} aria-label={`Editar ${variante.nombre}`} title="Editar variante">
          <i className="bi bi-pencil-square" aria-hidden="true"></i>
        </button>
        <button type="button" className="variante-icon-button is-danger" onClick={onDelete} aria-label={`Eliminar ${variante.nombre}`} title="Eliminar variante">
          <i className="bi bi-trash3" aria-hidden="true"></i>
        </button>
      </div>
    </div>
  );
}

function VarianteModal({ variante, esEdicion, nombresExistentes, onCancel, onSave }) {
  const [form, setForm] = useState(variante);
  const [errores, setErrores] = useState({});

  useEffect(() => {
    const cerrarConEscape = (event) => {
      if (event.key === "Escape") onCancel();
    };
    document.body.classList.add("modal-open");
    window.addEventListener("keydown", cerrarConEscape);
    return () => {
      document.body.classList.remove("modal-open");
      window.removeEventListener("keydown", cerrarConEscape);
    };
  }, [onCancel]);

  const actualizar = (campo, valor) => {
    setForm((actual) => ({ ...actual, [campo]: valor }));
    setErrores((actuales) => ({ ...actuales, [campo]: "" }));
  };

  const guardar = () => {
    const nuevosErrores = {};
    const nombre = form.nombre.trim();
    const precio = Number(form.precio);
    const orden = Number(form.orden);

    if (!nombre) nuevosErrores.nombre = "El nombre es obligatorio.";
    else if (nombresExistentes.includes(nombre.toLowerCase())) nuevosErrores.nombre = "Ya existe una variante con este nombre.";
    if (form.precio === "") nuevosErrores.precio = "El precio es obligatorio.";
    else if (!Number.isFinite(precio) || precio < 0) nuevosErrores.precio = "El precio debe ser mayor o igual a 0.";
    if (form.orden === "" || !Number.isInteger(orden) || orden < 0) {
      nuevosErrores.orden = "El orden debe ser un número entero mayor o igual a 0.";
    }

    if (Object.keys(nuevosErrores).length) {
      setErrores(nuevosErrores);
      return;
    }

    onSave({ ...form, nombre, precio: form.precio, orden: form.orden });
  };

  return (
    <div className="variante-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
      <section className="variante-modal" role="dialog" aria-modal="true" aria-labelledby="variante-modal-title">
        <header className="variante-modal-header">
          <div>
            <span>Variantes o tamaños</span>
            <h2 id="variante-modal-title">{esEdicion ? "Editar variante" : "Agregar variante"}</h2>
          </div>
          <button type="button" className="variante-modal-close" onClick={onCancel} aria-label="Cerrar modal">
            <i className="bi bi-x-lg" aria-hidden="true"></i>
          </button>
        </header>

        <div className="variante-modal-body">
          <div className="variante-field">
            <label htmlFor="variante-nombre">Nombre <span>*</span></label>
            <input id="variante-nombre" className={`form-control ${errores.nombre ? "is-invalid" : ""}`} value={form.nombre} placeholder="Ej: Familiar" onChange={(e) => actualizar("nombre", e.target.value)} autoFocus />
            {errores.nombre && <small className="variante-field-error">{errores.nombre}</small>}
          </div>
          <div className="variante-modal-grid">
            <div className="variante-field">
              <label htmlFor="variante-precio">Precio (CLP) <span>*</span></label>
              <input id="variante-precio" className={`form-control ${errores.precio ? "is-invalid" : ""}`} type="number" min="0" value={form.precio} placeholder="Ej: 18000" onChange={(e) => actualizar("precio", e.target.value)} />
              {errores.precio && <small className="variante-field-error">{errores.precio}</small>}
            </div>
            <div className="variante-field">
              <label htmlFor="variante-orden">Orden <span>*</span></label>
              <input id="variante-orden" className={`form-control ${errores.orden ? "is-invalid" : ""}`} type="number" min="0" step="1" value={form.orden} onChange={(e) => actualizar("orden", e.target.value)} />
              {errores.orden && <small className="variante-field-error">{errores.orden}</small>}
            </div>
          </div>
          <div className="variante-field">
            <label htmlFor="variante-descripcion">Descripción</label>
            <textarea id="variante-descripcion" className="form-control" rows="3" value={form.descripcion} placeholder="Ej: Ideal para 3 o 4 personas" onChange={(e) => actualizar("descripcion", e.target.value)}></textarea>
          </div>
          <label className="variante-active-control">
            <span><strong>Activa</strong><small>Disponible para seleccionar en la carta.</small></span>
            <input className="form-check-input" type="checkbox" checked={form.activo !== false} onChange={(e) => actualizar("activo", e.target.checked)} />
          </label>
        </div>

        <footer className="variante-modal-footer">
          <button type="button" className="variante-cancel-button" onClick={onCancel}>Cancelar</button>
          <button type="button" className="variante-save-button" onClick={guardar}>Guardar variante</button>
        </footer>
      </section>
    </div>
  );
}

export default function ProductoVariantesEditor({ variantes, onChange }) {
  const [modal, setModal] = useState(null);

  const abrirNueva = () => setModal({ index: null, variante: crearVariante(variantes.length) });
  const abrirEdicion = (index) => setModal({ index, variante: { ...variantes[index] } });
  const cerrarModal = () => setModal(null);

  const guardarVariante = (variante) => {
    if (modal.index === null) onChange([...variantes, variante]);
    else onChange(variantes.map((actual, index) => index === modal.index ? variante : actual));
    cerrarModal();
  };

  const eliminar = (index) => {
    if (!window.confirm("¿Seguro que deseas eliminar esta variante?")) return;
    onChange(variantes.filter((_, i) => i !== index));
  };

  const nombresExistentes = modal
    ? variantes.filter((_, index) => index !== modal.index).map((item) => item.nombre.trim().toLowerCase())
    : [];

  return (
    <div className="form mt-4 variantes-editor">
      <div className="variantes-editor-header">
        <div>
          <p className="info-header"><span><i className="bi bi-layers"></i></span>{" "}Variantes o tamaños</p>
          <small>Opcional. Ejemplos: Individual, Mediana o Familiar.</small>
        </div>
        <button type="button" className="variantes-add-button" onClick={abrirNueva}>
          <i className="bi bi-plus-lg" aria-hidden="true"></i> Agregar variante
        </button>
      </div>

      {variantes.length === 0 ? (
        <p className="variantes-empty">Este producto usará su precio actual.</p>
      ) : (
        <div className="variantes-list" role="table" aria-label="Variantes del producto">
          <div className="variantes-list-header" role="row">
            <span role="columnheader">Variante</span><span role="columnheader">Precio</span><span role="columnheader">Estado</span><span role="columnheader">Orden</span><span role="columnheader">Acciones</span>
          </div>
          {variantes.map((variante, index) => (
            <VarianteRow key={variante.id || `nueva-${index}`} variante={variante} onEdit={() => abrirEdicion(index)} onDelete={() => eliminar(index)} />
          ))}
        </div>
      )}

      {modal && <VarianteModal variante={modal.variante} esEdicion={modal.index !== null} nombresExistentes={nombresExistentes} onCancel={cerrarModal} onSave={guardarVariante} />}
    </div>
  );
}
