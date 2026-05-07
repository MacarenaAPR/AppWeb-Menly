import { useCallback, useEffect, useState } from "react";
import { authFetch } from "../../api";


export default function CategoriasConfig() {
  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [modalAbierto, setModalAbierto] = useState(false);
  const [categoriaEditando, setCategoriaEditando] = useState(null);
  const [form, setForm] = useState({
    nombre: "",
    orden: 0,
    activa: true,
    icono:"",
  });
  const [iconos, setIconos] = useState([]);
  const restauranteStorage = JSON.parse(localStorage.getItem("restaurante") || "null");
  const esDueno = restauranteStorage?.rol === "dueno";
  const puedeToggle = ["dueno", "admin"].includes(restauranteStorage?.rol);
  const cargarIconos = useCallback(async () => {
    try {
      const response = await authFetch("/iconos/");
      const data = await response.json();

      if (!response.ok) return;

      setIconos(data || []);
    } catch {
      setError("No se pudieron cargar los iconos");
    }
  }, []);
  const cargarCategorias = useCallback(async () => {
    try {
      setError("");

      const response = await authFetch("/mi-restaurante/categorias/");

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudieron cargar las categorías");
        return;
      }

      setCategorias(data || []);
    } catch {
      setError("No se pudieron cargar las categorías");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarCategorias();
    cargarIconos();
  }, [cargarCategorias, cargarIconos]);

  const abrirCrear = () => {
    setCategoriaEditando(null);
    setForm({
      nombre: "",
      orden: categorias.length + 1,
      activa: true,
      icono: "",
    });
    setModalAbierto(true);
  };

  const abrirEditar = (categoria) => {
    setCategoriaEditando(categoria);
    setForm({
      nombre: categoria.nombre || "",
      orden: categoria.orden ?? 0,
      activa: categoria.activa ?? true,
      icono: categoria.icono || "",
    });
    setModalAbierto(true);
  };

  const cerrarModal = () => {
    setModalAbierto(false);
    setCategoriaEditando(null);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    setForm({
      ...form,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const guardarCategoria = async (e) => {
    e.preventDefault();

    try {
      setError("");
      setSuccess("");

      const endpoint = categoriaEditando
        ? `/mi-restaurante/categorias/${categoriaEditando.id}/`
        : "/mi-restaurante/categorias/";

      const response = await authFetch(endpoint, {
        method: categoriaEditando ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          nombre: form.nombre,
          orden: Number(form.orden || 0),
          activa: form.activa,
          icono: form.icono || null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || data.nombre?.[0] || "No se pudo guardar la categoría");
        return;
      }

      cerrarModal();
      setSuccess("Categoría guardada correctamente");
      cargarCategorias();
    } catch {
      setError("No se pudo guardar la categoría");
    }
  };

  const eliminarCategoria = async (categoria) => {
    const confirmar = window.confirm(`Seguro que quieres eliminar "${categoria.nombre}"?`);
    if (!confirmar) return;

    try {
      setError("");
      setSuccess("");

      const response = await authFetch(`/mi-restaurante/categorias/${categoria.id}/`, {
        method: "DELETE",
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudo eliminar la categoría");
        return;
      }

      setSuccess(data.mensaje || "Categoría eliminada correctamente");
      cargarCategorias();
    } catch {
      setError("No se pudo eliminar la categoría");
    }
  };

  const toggleCategoria = async (categoria) => {
    try {
      setError("");
      setSuccess("");

      const response = await authFetch(`/mi-restaurante/categorias/${categoria.id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          activa: !categoria.activa,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudo cambiar el estado de la categoría");
        return;
      }

      setSuccess(categoria.activa ? "Categoría desactivada" : "Categoría activada");
      cargarCategorias();
    } catch {
      setError("No se pudo cambiar el estado de la categoría");
    }
  };

  if (loading) return <p>Cargando categorías...</p>;

  return (
    <div className="categorias-panel">
      <div className="usuarios-title">
        <i className="bi bi-tag"></i>
        <div>
          <h2>Categorías del restaurante</h2>
          <p>Organiza las secciones que se muestran en la carta.</p>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}
      {success && <p className="success-text">{success}</p>}

      <section className="usuarios-card categorias-list-card">
        <div className="categorias-card-header">
          <h3>Lista de categorías</h3>

          {esDueno && (
            <button className="usuarios-create-btn" type="button" onClick={abrirCrear}>
              <i className="bi bi-plus-lg"></i>
              Nueva categoría
            </button>
          )}
        </div>

        <div className="categorias-table">
          <div className="categorias-table-head">
            <span>Nombre</span>
            <span>Orden</span>
            <span>Estado</span>
            {puedeToggle && <span>Acciones</span>}
          </div>

          <div className="categorias-table-body">
            {categorias.length === 0 ? (
              <p className="empty-text">No hay categorías registradas.</p>
            ) : (
              categorias.map((categoria) => (
                <div key={categoria.id} className="categorias-row">
                  <strong className="categoria-nombre-icono">
                    <i className={categoria.icono_detalle?.clase_css || "fa-solid fa-tag"}></i>
                    {categoria.nombre}
                  </strong>
                  <span>{categoria.orden ?? "-"}</span>
                  <span
                    className={
                      categoria.activa === false
                        ? "usuarios-status inactive"
                        : "usuarios-status active"
                    }
                  >
                    {categoria.activa === false ? "Inactiva" : "Activa"}
                  </span>

                  {puedeToggle && (
                    <div className="usuarios-actions">
                      {esDueno && (
                      <button
                        type="button"
                        className="usuarios-edit-btn"
                        onClick={() => abrirEditar(categoria)}
                      >
                        Editar
                      </button>
                      )}
                      <button
                        type="button"
                        className="usuarios-toggle-btn"
                        onClick={() => toggleCategoria(categoria)}
                      >
                        {categoria.activa === false ? "Activar" : "Desactivar"}
                      </button>
                      {esDueno && (
                      <button
                        type="button"
                        className="usuarios-delete-btn"
                        onClick={() => eliminarCategoria(categoria)}
                      >
                        Eliminar
                      </button>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      {modalAbierto && esDueno && (
        <div className="config-modal-backdrop">
          <section className="usuarios-card config-modal-card">
            <h3>{categoriaEditando ? "Editar categoría" : "Nueva categoría"}</h3>

            <form className="usuarios-form" onSubmit={guardarCategoria}>
              <label>
                Icono
                <div className="iconos-selector">
                  {iconos.map((icono) => (
                    <button
                      key={icono.id}
                      type="button"
                      className={
                        form.icono === icono.id
                          ? "icono-btn active"
                          : "icono-btn"
                      }
                      onClick={() =>
                        setForm({
                          ...form,
                          icono: icono.id,
                        })
                      }
                      title={icono.nombre}
                    >
                      <i className={icono.clase_css}></i>
                    </button>
                  ))}
                </div>
              </label>
              <label>
                Nombre
                <input
                  name="nombre"
                  placeholder="Ej: Sandwiches"
                  value={form.nombre}
                  onChange={handleChange}
                  required
                />
              </label>

              <label>
                Orden
                <input
                  name="orden"
                  type="number"
                  min="0"
                  value={form.orden}
                  onChange={handleChange}
                />
              </label>

              <label className="categorias-check">
                <input
                  name="activa"
                  type="checkbox"
                  checked={form.activa}
                  onChange={handleChange}
                />
                Categoría activa
              </label>

              <div className="usuarios-edit-actions">
                <button type="button" className="usuarios-cancel-btn" onClick={cerrarModal}>
                  Cancelar
                </button>
                <button type="submit" className="usuarios-save-btn">
                  Guardar
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
