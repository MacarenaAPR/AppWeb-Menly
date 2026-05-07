import { useCallback, useEffect, useState } from "react";
import { authFetch } from "../../api";


export default function IntegracionesConfig() {
  const [form, setForm] = useState({
    whatsapp: "",
    instagram: "",
    facebook: "",
    google_maps: "",
    sitio_web: "",
    link_delivery: "",
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const cargarIntegraciones = useCallback(async () => {
    try {
      const response = await authFetch("/mi-restaurante/configuracion/");

      const data = await response.json();

      if (!response.ok) {
        setError("No se pudieron cargar las integraciones");
        return;
      }

      const restaurante = data.restaurante || data;

      setForm({
        whatsapp: restaurante.whatsapp || "",
        instagram: restaurante.instagram || "",
        facebook: restaurante.facebook || "",
        google_maps: restaurante.google_maps || "",
        sitio_web: restaurante.sitio_web || "",
        link_delivery: restaurante.link_delivery || "",
      });
    } catch {
      setError("No se pudieron cargar las integraciones");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarIntegraciones();
  }, [cargarIntegraciones]);

  const handleChange = (e) => {
    const { name, value } = e.target;

    setForm({
      ...form,
      [name]: value,
    });
  };

  const guardarIntegraciones = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const response = await authFetch("/mi-restaurante/configuracion/", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "No se pudieron guardar las integraciones");
        return;
      }

      setSuccess("Integraciones guardadas correctamente");
    } catch {
      setError("No se pudieron guardar las integraciones");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p>Cargando integraciones...</p>;

  return (
    <div className="integraciones-panel">
      <div className="usuarios-title">
        <i className="bi bi-link-45deg"></i>
        <div>
          <h2>Integraciones</h2>
          <p>Conecta tus canales externos con la página del restaurante.</p>
        </div>
      </div>

      <section className="usuarios-card">
        <h3>Canales externos</h3>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <p className="success-text">{success}</p>}

        <form className="usuarios-form" onSubmit={guardarIntegraciones}>
          <label>
            WhatsApp
            <input
              type="text"
              name="whatsapp"
              value={form.whatsapp}
              onChange={handleChange}
              placeholder="Ej: 56912345678"
            />
          </label>

          <label>
            Instagram
            <input
              type="url"
              name="instagram"
              value={form.instagram}
              onChange={handleChange}
              placeholder="https://instagram.com/tu_restaurante"
            />
          </label>

          <label>
            Facebook
            <input
              type="url"
              name="facebook"
              value={form.facebook}
              onChange={handleChange}
              placeholder="https://facebook.com/tu_restaurante"
            />
          </label>

          <label>
            Google Maps
            <input
              type="url"
              name="google_maps"
              value={form.google_maps}
              onChange={handleChange}
              placeholder="https://maps.google.com/..."
            />
          </label>

          <label>
            Sitio web
            <input
              type="url"
              name="sitio_web"
              value={form.sitio_web}
              onChange={handleChange}
              placeholder="https://turestaurante.cl"
            />
          </label>

          <label>
            Link delivery externo
            <input
              type="url"
              name="link_delivery"
              value={form.link_delivery}
              onChange={handleChange}
              placeholder="https://pedidosya.cl/..."
            />
          </label>

          <div className="usuarios-edit-actions">
            <button
              type="submit"
              className="usuarios-save-btn"
              disabled={saving}
            >
              {saving ? "Guardando..." : "Guardar cambios"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

