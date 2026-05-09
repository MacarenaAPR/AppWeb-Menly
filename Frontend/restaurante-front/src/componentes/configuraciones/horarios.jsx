import { useCallback, useEffect, useState } from "react";
import { authFetch } from "../../api";


const DIAS = [
  { value: 1, label: "Lunes" },
  { value: 2, label: "Martes" },
  { value: 3, label: "Miércoles" },
  { value: 4, label: "Jueves" },
  { value: 5, label: "Viernes" },
  { value: 6, label: "Sábado" },
  { value: 7, label: "Domingo" },
];

export default function HorariosConfig({ onUpdate }) {
  const [horarios, setHorarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [modalAbierto, setModalAbierto] = useState(false);
  const [horarioEditando, setHorarioEditando] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    dia: "1",
    hora_apertura: "",
    hora_cierre: "",
    cerrado: false,
    activo: true,
  });

  const restauranteStorage = JSON.parse(localStorage.getItem("restaurante") || "null");
  const esDueno = restauranteStorage?.rol === "dueno";
  const puedeCambiarAbiertoCerrado = ["dueno", "admin"].includes(restauranteStorage?.rol);

  const cargarHorarios = useCallback(async () => {
    try {
      setError("");

      const response = await authFetch("/mi-restaurante/horarios/");

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudieron cargar los horarios");
        return;
      }

      setHorarios(data || []);
    } catch {
      setError("No se pudieron cargar los horarios");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarHorarios();
  }, [cargarHorarios]);

  const abrirEditar = (horario) => {
    setHorarioEditando(horario);
    setForm({
      dia: String(horario.dia || 1),
      hora_apertura: horario.hora_apertura || "",
      hora_cierre: horario.hora_cierre || "",
      cerrado: horario.cerrado ?? false,
      activo: horario.activo ?? true,
    });
    setModalAbierto(true);
  };

  const cerrarModal = () => {
    setModalAbierto(false);
    setHorarioEditando(null);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    setForm({
      ...form,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const guardarHorario = async (e) => {
    e.preventDefault();
    setSaving(true);

    try {
      setError("");
      setSuccess("");

      const endpoint = horarioEditando
        ? `/mi-restaurante/horarios/${horarioEditando.id}/`
        : "/mi-restaurante/horarios/";

      const payload = {
        dia: Number(form.dia),
        hora_apertura: form.cerrado ? null : form.hora_apertura,
        hora_cierre: form.cerrado ? null : form.hora_cierre,
        cerrado: form.cerrado,
        activo: form.activo,
      };

      const response = await authFetch(endpoint, {
        method: horarioEditando ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(
          data.error ||
            data.dia?.[0] ||
            data.hora_apertura?.[0] ||
            data.hora_cierre?.[0] ||
            "No se pudo guardar el horario"
        );
        return;
      }

      cerrarModal();
      setSuccess("Horario guardado correctamente");
      await cargarHorarios();
      if (onUpdate) await onUpdate();
    } catch {
      setError("No se pudo guardar el horario");
    } finally {
      setSaving(false);
    }
  };

 
 
  const toggleAbiertoCerrado = async (horario) => {
    try {
      setError("");
      setSuccess("");

      const response = await authFetch(`/mi-restaurante/horarios/${horario.id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          cerrado: !horario.cerrado,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudo cambiar el estado abierto/cerrado");
        return;
      }

      setSuccess(horario.cerrado ? "Horario abierto" : "Horario cerrado");
      await cargarHorarios();
      if (onUpdate) await onUpdate();
    } catch {
      setError("No se pudo cambiar el estado abierto/cerrado");
    }
  };

  const getDiaNombre = (horario) => {
    return horario.dia_nombre || DIAS.find((dia) => dia.value === Number(horario.dia))?.label || "-";
  };

  const formatearHora = (hora) => {
    if (!hora) return "--:--";
    return String(hora).slice(0, 5);
  };

  const formatearRango = (horario) => {
    if (horario.cerrado) return "Cerrado";
    return `${formatearHora(horario.hora_apertura)} - ${formatearHora(horario.hora_cierre)}`;
  };

  const horariosOrdenados = [...horarios].sort((a, b) => Number(a.dia) - Number(b.dia));

  if (loading) return <p>Cargando horarios...</p>;

  return (
    <div className="horarios-panel">
      <div className="usuarios-title">
        <i className="bi bi-clock"></i>
        <div>
          <h2>Horarios de atención</h2>
          <p>Configura los días abiertos, cierres y rangos de atención.</p>
        </div>
      </div>

      {error && <p className="empty-text">{error}</p>}
      {success && <p className="success-text">{success}</p>}

      <section className="usuarios-card horarios-list-card">
        <div className="categorias-card-header">
          <h3>Lista de horarios</h3>

        </div>

        <div className="horarios-table">
          <div className="horarios-table-head">
            <span>Dia</span>
            <span>Horario</span>
            <span>Estado</span>
            {puedeCambiarAbiertoCerrado && <span>Acciones</span>}
          </div>

          <div className="horarios-table-body">
            {horariosOrdenados.length === 0 ? (
              <p className="empty-text">No hay horarios registrados.</p>
            ) : (
              horariosOrdenados.map((horario) => (
                <div key={horario.id} className="horarios-row">
                  <strong>{getDiaNombre(horario)}</strong>
                  <span>{formatearRango(horario)}</span>
                  <span className={horario.activo ? "usuarios-status active" : "usuarios-status inactive"}>
                    {horario.activo ? "Activo" : "Inactivo"}
                  </span>

                  {puedeCambiarAbiertoCerrado && (
                    <div className="usuarios-actions">
                      {esDueno && (
                      <button
                        type="button"
                        className="usuarios-edit-btn"
                        onClick={() => abrirEditar(horario)}
                      >
                        Editar
                      </button>
                      )}
                      {esDueno && (
                      <button
                        type="button"
                        className="usuarios-toggle-btn"
                        onClick={() => toggleAbiertoCerrado(horario)}
                      >
                        {horario.cerrado ? "Abrir" : "Cerrar"}
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
            <h3>{horarioEditando ? "Editar horario" : "Nuevo horario"}</h3>

            <form className="usuarios-form" onSubmit={guardarHorario}>
              <label>
                Día
                <select name="dia" value={form.dia} onChange={handleChange}>
                  {DIAS.map((dia) => (
                    <option key={dia.value} value={dia.value}>
                      {dia.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Apertura
                <input
                  name="hora_apertura"
                  type="time"
                  value={form.hora_apertura}
                  onChange={handleChange}
                  disabled={form.cerrado}
                  required={!form.cerrado}
                />
              </label>

              <label>
                Cierre
                <input
                  name="hora_cierre"
                  type="time"
                  value={form.hora_cierre}
                  onChange={handleChange}
                  disabled={form.cerrado}
                  required={!form.cerrado}
                />
              </label>

              <label className="categorias-check">
                <input
                  name="cerrado"
                  type="checkbox"
                  checked={form.cerrado}
                  onChange={handleChange}
                />
                Día cerrado
              </label>

              <label className="categorias-check">
                <input
                  name="activo"
                  type="checkbox"
                  checked={form.activo}
                  onChange={handleChange}
                />
                Horario activo
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
