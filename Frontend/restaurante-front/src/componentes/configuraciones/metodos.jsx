import { useCallback, useEffect, useState } from "react";
import { authFetch } from "../../api";

export default function MetodoPago({onUpdate}) {
  const [metodos, setMetodos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [modalAbierto, setModalAbierto] = useState(false);
  const [editando, setEditando] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    nombre: "",
    activo: true,
  });

  const restauranteStorage = JSON.parse(localStorage.getItem("restaurante") || "null");
  const esDueno = restauranteStorage?.rol === "dueno";
  const puedeToggle = ["dueno", "admin"].includes(restauranteStorage?.rol);

  const cargarMetodos = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await authFetch("/mi-restaurante/metodos-pago/");
      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "Error al cargar métodos de pago");
        return;
      }

      setMetodos(data || []);
    } catch {
      setError("Error al cargar métodos de pago");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarMetodos();
  }, [cargarMetodos]);

  const abrirModalCrear = () => {
    setEditando(null);
    setForm({
      nombre: "",
      activo: true,
    });
    setError("");
    setSuccess("");
    setModalAbierto(true);
  };

  const abrirModalEditar = (metodo) => {
    setEditando(metodo);
    setForm({
      nombre: metodo.nombre || "",
      activo: metodo.activo ?? true,
    });
    setError("");
    setSuccess("");
    setModalAbierto(true);
  };

  const cerrarModal = () => {
    setModalAbierto(false);
    setEditando(null);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    setForm({
      ...form,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const guardarMetodo = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const endpoint = editando
        ? `/mi-restaurante/metodos-pago/${editando.id}/`
        : "/mi-restaurante/metodos-pago/";

      const response = await authFetch(endpoint, {
        method: editando ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || data.nombre?.[0] || "No se pudo guardar el método de pago");
        return;
      }

      cerrarModal();
      setSuccess("Método de pago guardado correctamente");
      cargarMetodos();
      if (onUpdate) await onUpdate();
    } catch {
      setError("No se pudo guardar el método de pago");
    } finally {
      setSaving(false);
    }
  };

  const cambiarEstadoMetodo = async (metodo) => {
    try {
      setError("");
      setSuccess("");

      const response = await authFetch(`/mi-restaurante/metodos-pago/${metodo.id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          activo: !metodo.activo,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudo cambiar el estado del método de pago");
        return;
      }

      setSuccess(metodo.activo ? "Método de pago desactivado" : "Método de pago activado");
      await cargarMetodos();
      if (onUpdate) await onUpdate();
    } catch {
      setError("No se pudo cambiar el estado del método de pago");
    }
  };

  const eliminarMetodo = async (metodo) => {
    const confirmar = window.confirm(`Seguro que quieres eliminar "${metodo.nombre}"?`);
    if (!confirmar) return;

    try {
      setError("");
      setSuccess("");

      const response = await authFetch(`/mi-restaurante/metodos-pago/${metodo.id}/`, {
        method: "DELETE",
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudo eliminar el método de pago");
        return;
      }

      setSuccess(data.mensaje || "Método de pago eliminado correctamente");
      await cargarMetodos();
      if (onUpdate) await onUpdate();
    } catch {
      setError("No se pudo eliminar el método de pago");
    }
  };

  if (loading) return <p>Cargando métodos de pago...</p>;

  return (
    <div className="metodos-panel">
      <div className="usuarios-title">
        <i className="bi bi-credit-card"></i>
        <div>
          <h2>Métodos de pago</h2>
          <p>Configura cómo pueden pagar tus clientes.</p>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}
      {success && <p className="success-text">{success}</p>}

      <section className="usuarios-card metodos-list-card">
        <div className="categorias-card-header">
          <h3>Lista de métodos de pago</h3>

          {esDueno && (
            <button className="usuarios-create-btn" type="button" onClick={abrirModalCrear}>
              <i className="bi bi-plus-lg"></i>
              Nuevo método
            </button>
          )}
        </div>

        <div className="metodos-table">
          <div className="metodos-table-head">
            <span>Nombre</span>
            <span>Estado</span>
            {puedeToggle && <span>Acciones</span>}
          </div>

          <div className="metodos-table-body">
            {metodos.length === 0 ? (
              <p className="empty-text">No hay métodos de pago registrados.</p>
            ) : (
              metodos.map((metodo) => (
                <div key={metodo.id} className="metodos-row">
                  <strong>{metodo.nombre}</strong>
                  <span className={metodo.activo ? "usuarios-status active" : "usuarios-status inactive"}>
                    {metodo.activo ? "Activo" : "Inactivo"}
                  </span>

                  {puedeToggle && (
                    <div className="usuarios-actions">
                      {esDueno && (
                      <button
                        type="button"
                        className="usuarios-edit-btn"
                        onClick={() => abrirModalEditar(metodo)}
                      >
                        Editar
                      </button>
                      )}
                      <button
                        type="button"
                        className="usuarios-toggle-btn"
                        onClick={() => cambiarEstadoMetodo(metodo)}
                      >
                        {metodo.activo ? "Desactivar" : "Activar"}
                      </button>
                      {esDueno && (
                      <button
                        type="button"
                        className="usuarios-delete-btn"
                        onClick={() => eliminarMetodo(metodo)}
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
            <h3>{editando ? "Editar método" : "Nuevo método"}</h3>

            <form className="usuarios-form" onSubmit={guardarMetodo}>
              <label>
                Nombre
                <input
                  name="nombre"
                  placeholder="Ej: Efectivo, Transferencia, Débito"
                  value={form.nombre}
                  onChange={handleChange}
                  required
                />
              </label>

              <label className="categorias-check">
                <input
                  name="activo"
                  type="checkbox"
                  checked={form.activo}
                  onChange={handleChange}
                />
                Método activo
              </label>

              <div className="usuarios-edit-actions">
                <button type="button" className="usuarios-cancel-btn" onClick={cerrarModal}>
                  Cancelar
                </button>
                <button type="submit" className="usuarios-save-btn" disabled={saving}>
                  {saving ? "Guardando..." : "Guardar"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
