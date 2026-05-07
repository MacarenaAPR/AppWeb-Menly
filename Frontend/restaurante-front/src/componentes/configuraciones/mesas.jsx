import { useCallback, useEffect, useState } from "react";
import { authFetch } from "../../api";


export default function MesasConfig({onUpdate}) {
  const [mesas, setMesas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [modalAbierto, setModalAbierto] = useState(false);
  const [mesaEditando, setMesaEditando] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    numero: "",
    nombre: "",
    activa: true,
  });

  const restauranteStorage = JSON.parse(localStorage.getItem("restaurante") || "null");
  const esDueno = restauranteStorage?.rol === "dueno";
  const puedeToggle = ["dueno", "admin"].includes(restauranteStorage?.rol);

  const cargarMesas = useCallback(async () => {
    try {
      setError("");

      const response = await authFetch("/mi-restaurante/mesas/");

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudieron cargar las mesas");
        return;
      }

      setMesas(data || []);
    } catch {
      setError("No se pudieron cargar las mesas");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarMesas();
  }, [cargarMesas]);

  const abrirCrear = () => {
    setMesaEditando(null);
    setForm({
      numero: "",
      nombre: "",
      activa: true,
    });
    setModalAbierto(true);
  };

  const abrirEditar = (mesa) => {
    setMesaEditando(mesa);
    setForm({
      numero: mesa.numero ?? "",
      nombre: mesa.nombre || "",
      activa: mesa.activa ?? true,
    });
    setModalAbierto(true);
  };

  const cerrarModal = () => {
    setModalAbierto(false);
    setMesaEditando(null);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    setForm({
      ...form,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const guardarMesa = async (e) => {
    e.preventDefault();
    setSaving(true);

    try {
      setError("");
      setSuccess("");

      const endpoint = mesaEditando
        ? `/mi-restaurante/mesas/${mesaEditando.id}/`
        : "/mi-restaurante/mesas/";

      const response = await authFetch(endpoint, {
        method: mesaEditando ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          numero: Number(form.numero),
          nombre: form.nombre,
          activa: form.activa,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || data.numero?.[0] || "No se pudo guardar la mesa");
        return;
      }

      cerrarModal();
      setSuccess("Mesa guardada correctamente");
      await cargarMesas();
      if (onUpdate) await onUpdate();
    } catch {
      setError("No se pudo guardar la mesa");
    } finally {
      setSaving(false);
    }
  };

  const eliminarMesa = async (mesa) => {
    const confirmar = window.confirm(`¿Seguro que quieres eliminar la mesa ${mesa.numero}?`);
    if (!confirmar) return;

    try {
      setError("");
      setSuccess("");

      const response = await authFetch(`/mi-restaurante/mesas/${mesa.id}/`, {
        method: "DELETE",
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(data.error || data.detail || "No se pudo eliminar la mesa");
        return;
      }

      setSuccess(data.mensaje || "Mesa eliminada correctamente");
      await cargarMesas();
      if (onUpdate) await onUpdate();
    } catch {
      setError("No se pudo eliminar la mesa");
    }
  };

  const toggleMesa = async (mesa) => {
    try {
      setError("");
      setSuccess("");

      const response = await authFetch(`/mi-restaurante/mesas/${mesa.id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          activa: !mesa.activa,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudo cambiar el estado de la mesa");
        return;
      }

      setSuccess(mesa.activa ? "Mesa desactivada" : "Mesa activada");
      await cargarMesas();
      if (onUpdate) await onUpdate();
    } catch {
      setError("No se pudo cambiar el estado de la mesa");
    }
  };

  if (loading) return <p>Cargando mesas...</p>;

  return (
    <div className="mesas-panel">
      <div className="usuarios-title">
        <i className="bi bi-table"></i>
        <div>
          <h2>Mesas del restaurante</h2>
          <p>Administra la numeracion, nombres y estado operativo de tus mesas.</p>
        </div>
      </div>

      {error && <p className="empty-text">{error}</p>}
      {success && <p className="success-text">{success}</p>}

      <section className="usuarios-card mesas-list-card">
        <div className="categorias-card-header">
          <h3>Lista de mesas</h3>

          {esDueno && (
            <button className="usuarios-create-btn" type="button" onClick={abrirCrear}>
              <i className="bi bi-plus-lg"></i>
              Nueva mesa
            </button>
          )}
        </div>

        <div className="mesas-table">
          <div className="mesas-table-head">
            <span>Numero</span>
            <span>Nombre</span>
            <span>Estado</span>
            {puedeToggle && <span>Acciones</span>}
          </div>

          <div className="mesas-table-body">
            {mesas.length === 0 ? (
              <p className="empty-text">No hay mesas registradas.</p>
            ) : (
              mesas.map((mesa) => (
                <div key={mesa.id} className="mesas-row">
                  <strong>Mesa {mesa.numero}</strong>
                  <span>{mesa.nombre || "-"}</span>
                  <span className={mesa.activa ? "usuarios-status active" : "usuarios-status inactive"}>
                    {mesa.activa ? "Activa" : "Inactiva"}
                  </span>

                  {puedeToggle && (
                    <div className="usuarios-actions">
                      {esDueno && (
                      <button
                        type="button"
                        className="usuarios-edit-btn"
                        onClick={() => abrirEditar(mesa)}
                      >
                        Editar
                      </button>
                      )}
                      <button
                        type="button"
                        className="usuarios-toggle-btn"
                        onClick={() => toggleMesa(mesa)}
                      >
                        {mesa.activa ? "Desactivar" : "Activar"}
                      </button>
                      {esDueno && (
                      <button
                        type="button"
                        className="usuarios-delete-btn"
                        onClick={() => eliminarMesa(mesa)}
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
            <h3>{mesaEditando ? "Editar mesa" : "Nueva mesa"}</h3>

            <form className="usuarios-form" onSubmit={guardarMesa}>
              <label>
                Numero
                <input
                  name="numero"
                  type="number"
                  min="1"
                  placeholder="Ej: 1"
                  value={form.numero}
                  onChange={handleChange}
                  required
                />
              </label>

              <label>
                Nombre opcional
                <input
                  name="nombre"
                  placeholder="Ej: Terraza"
                  value={form.nombre}
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
                Mesa activa
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
