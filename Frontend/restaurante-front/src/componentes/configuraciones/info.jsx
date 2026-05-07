import { useEffect, useState } from "react";
import { authFetch, buildMediaUrl } from "../../api";


const getLogoUrl = (restaurante, previewFile) => {
  if (previewFile) {
    return URL.createObjectURL(previewFile);
  }

  const logo = restaurante?.logo_url || restaurante?.logo;

  if (!logo) return "";

  if (typeof logo === "string" && logo.startsWith("http")) {
    return logo;
  }

  if (typeof logo === "string" && logo.startsWith("/")) {
    return buildMediaUrl(logo);
  }

  return String(logo);
};

export default function InfoRestaurante({ restaurante, onUpdate, readOnly = false }) {
  const [form, setForm] = useState({
    nombre_empresa: "",
    descripcion: "",
    telefono: "",
    email_contacto: "",
    direccion: "",
    sitio_web: "",
    
  });

  const [logoFile, setLogoFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (restaurante) {
      setForm({
        nombre_empresa: restaurante.nombre_empresa || "",
        descripcion: restaurante.descripcion || "",
        telefono: restaurante.telefono || "",
        email_contacto: restaurante.email_contacto || "",
        direccion: restaurante.direccion || "",
        sitio_web: restaurante.sitio_web || "",

      });
    }
  }, [restaurante]);

  const handleChange = (e) => {
    const { name, value } = e.target;

    setForm({
      ...form,
      [name]: value,
    });
  };

  const handleLogoChange = (e) => {
    if (readOnly) return;

    const file = e.target.files?.[0];

    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setError("Selecciona una imagen válida");
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setError("La imagen no puede superar los 2MB");
      return;
    }

    setLogoFile(file);
  };

  const subirLogo = async () => {
    if (!logoFile) return null;

    const formData = new FormData();

    formData.append("logo", logoFile);

    const response = await authFetch("/mi-restaurante/upload-logo/", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("No se pudo subir el logo");
    }

    return await response.json();
  };

  const handleGuardarCambios = async () => {
    if (readOnly) return;

    try {
      setSaving(true);
      setError("");
      setSuccess("");

      let logoActualizado = null;

      if (logoFile) {
        logoActualizado = await subirLogo();
      }

      const response = await authFetch("/mi-restaurante/configuracion/", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        throw new Error("No se pudieron guardar los cambios");
      }

      const updated = await response.json();

      onUpdate({
        ...updated,
        logo: logoActualizado?.logo || updated.logo,
      });

      setLogoFile(null);
      setSuccess("Cambios guardados correctamente");
    } catch (error) {
      setError(error.message);
    } finally {
      setSaving(false);
    }
  };

  if (!restaurante) return null;

  const logoSrc = getLogoUrl(restaurante, logoFile);

  return (
    <div className="config-card config-card-main">
      <div className="card-title">
        <i className="bi bi-info-circle"></i>
        <div>
          <h2>Información del restaurante</h2>
          <p>Actualiza los datos principales de tu restaurante.</p>
        </div>
      </div>

      <div className="info-form-layout">
        <div className="logo-box">
          {logoSrc ? (
            <img
              src={logoSrc}
              alt={form.nombre_empresa}
            />
          ) : (
            <div className="logo-placeholder">
              <i className="bi bi-shop"></i>
            </div>
          )}

          <input
            id="logoInput"
            type="file"
            accept="image/*"
            onChange={handleLogoChange}
            hidden
          />

          {!readOnly && (
          <label htmlFor="logoInput" className="btn-camera">
            <i className="bi bi-camera"></i>
          </label>
          )}

          <small>JPG o PNG. Máx 2MB</small>
        </div>

        <div className="form-grid">
          {error && <div className="alert alert-danger full">{error}</div>}
          {success && <p className="success-text full">{success}</p>}

          <label>
            Nombre del restaurante
            <input
              name="nombre_empresa"
              value={form.nombre_empresa}
              onChange={handleChange}
              disabled={readOnly}
            />
          </label>

          <label>
            Descripción
            <textarea
              name="descripcion"
              value={form.descripcion}
              onChange={handleChange}
              disabled={readOnly}
            />
          </label>

          <label>
            Teléfono
            <input
              name="telefono"
              value={form.telefono}
              onChange={handleChange}
              disabled={readOnly}
            />
          </label>

          <label>
            Correo electrónico
            <input
              name="email_contacto"
              value={form.email_contacto}
              onChange={handleChange}
              disabled={readOnly}
            />
          </label>

          <label className="full">
            Dirección
            <input
              name="direccion"
              value={form.direccion}
              onChange={handleChange}
              disabled={readOnly}
            />
          </label>

          <label className="full">
            Sitio web
            <input
                placeholder="https://www.tudominio.com"
              name="sitio_web"
              value={form.sitio_web}
              onChange={handleChange}
              disabled={readOnly}
            />
          </label>

          {!readOnly && (
          <button
            className="btn-save"
            type="button"
            onClick={handleGuardarCambios}
            disabled={saving}
          >
            <i className="bi bi-save"></i>
            {saving ? "Guardando..." : "Guardar cambios"}
          </button>
          )}
        </div>
      </div>
    </div>
  );
}


