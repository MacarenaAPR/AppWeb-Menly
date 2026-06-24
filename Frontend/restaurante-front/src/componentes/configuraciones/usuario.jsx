import { useCallback, useEffect, useState } from "react";
import { authFetch } from "../../api";
import { formatearRolVisual } from "../../utils/permisos";


export default function UsuariosConfig() {
  const [usuarios, setUsuarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [usuarioEditando, setUsuarioEditando] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    rol: "empleado",
  });

  const cargarUsuarios = useCallback(async () => {
    try {
      setError("");

      const res = await authFetch("/mi-restaurante/usuarios/");

      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "No se pudieron cargar los usuarios");
        return;
      }
      setUsuarios(data.results || data);
    } catch {
      setError("No se pudieron cargar los usuarios");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarUsuarios();
  }, [cargarUsuarios]);

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

  const crearUsuario = async (e) => {
    e.preventDefault();
    setSaving(true);

    try {
      setError("");
      setSuccess("");

      const res = await authFetch("/mi-restaurante/usuarios/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "No se pudo crear el usuario");
        return;
      }

      setSuccess("Usuario creado correctamente");
      cargarUsuarios();

      setForm({
        username: "",
        email: "",
        password: "",
        rol: "empleado",
      });
    } catch {
      setError("No se pudo crear el usuario");
    } finally {
      setSaving(false);
    }
  };

  const toggleUsuario = async (id) => {
    try {
      setError("");
      setSuccess("");

      const res = await authFetch(`/mi-restaurante/usuarios/${id}/`, {
        method: "PATCH",
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "No se pudo cambiar el estado del usuario");
        return;
      }

      setSuccess("Estado del usuario actualizado");
      cargarUsuarios();
    } catch {
      setError("No se pudo cambiar el estado del usuario");
    }
  };

  const editarUsuario = async (id, datos) => {
    try {
      const payload = {
        username: datos.username,
        email: datos.email,
        password: datos.password,
      };

      if (!payload.password) {
        delete payload.password;
      }

      setError("");
      setSuccess("");

      const res = await authFetch(`/mi-restaurante/usuarios/${id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "No se pudo editar el usuario");
        return;
      }

      setUsuarioEditando(null);
      setSuccess("Usuario editado correctamente");
      cargarUsuarios();
    } catch {
      setError("No se pudo editar el usuario");
    }
  };

  const eliminarUsuario = async (id) => {
    const confirmar = window.confirm("Seguro que quieres eliminar este usuario?");
    if (!confirmar) return;

    try {
      setError("");
      setSuccess("");

      const res = await authFetch(`/mi-restaurante/usuarios/${id}/`, {
        method: "DELETE",
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "No se pudo eliminar el usuario");
        return;
      }

      setSuccess("Usuario eliminado correctamente");
      cargarUsuarios();
    } catch {
      setError("No se pudo eliminar el usuario");
    }
  };

  if (loading) return <p>Cargando...</p>;

  return (
    <div className="usuarios-panel">
      <div className="usuarios-title">
        <i className="bi bi-person-gear"></i>
        <div>
          <h2>Usuarios del restaurante</h2>
          <p>Administra los accesos, estados y datos de tu equipo.</p>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}
      {success && <p className="success-text">{success}</p>}

      <section className="usuarios-card">
        <h3>Nuevo usuario</h3>

        <form className="usuarios-form" onSubmit={crearUsuario}>
          <label>
            Usuario
            <input
              name="username"
              placeholder="Ingrese usuario"
              value={form.username}
              onChange={handleChange}
              required
            />
          </label>

          <label>
            Email
            <input
              name="email"
              type="email"
              placeholder="Ingrese email"
              value={form.email}
              onChange={handleChange}
              required
            />
          </label>

          <label>
            Password
            <input
              name="password"
              type="password"
              placeholder="Ingrese password"
              value={form.password}
              onChange={handleChange}
              required
            />
          </label>

          <label>
            Rol
            <select name="rol" value={form.rol} onChange={handleChange}>
              <option value="empleado">Empleado</option>
              <option value="admin">Administrador</option>
            </select>
          </label>

          <button className="usuarios-create-btn" type="submit" disabled={saving}>
            <i className="bi bi-plus-lg"></i>
            {saving ? "Creando..." : "Crear usuario"}
          </button>
        </form>
      </section>

      <section className="usuarios-card usuarios-list-card">
        <h3>Lista de usuarios</h3>

        <div className="usuarios-table">
          <div className="usuarios-table-head">
            <span>Usuario</span>
            <span>Rol</span>
            <span>Estado</span>
            <span>Acción</span>
          </div>

          <div className="usuarios-table-body">
            {usuarios.length === 0 ? (
              <div className="usuarios-row">
                <span>No hay usuarios disponibles.</span>
              </div>
            ) : (
            usuarios.map((u) => (
              <div key={u.id} className="usuarios-row">
                <div className="usuarios-user">
                  <span className="usuarios-avatar">
                    {u.username?.charAt(0).toUpperCase() || "U"}
                  </span>
                  <strong>{u.username}</strong>
                </div>

                <span className={`usuarios-role role-${u.rol || "empleado"}`}>
                  {formatearRolVisual(u.rol)}
                </span>

                <span className={u.activo ? "usuarios-status active" : "usuarios-status inactive"}>
                  {u.activo ? "Activo" : "Desactivado"}
                </span>

                <div className="usuarios-actions">
                  <button
                    type="button"
                    className="usuarios-toggle-btn"
                    onClick={() => toggleUsuario(u.id)}
                  >
                    {u.activo ? "Desactivar" : "Activar"}
                  </button>
                  <button
                    type="button"
                    className="usuarios-edit-btn"
                    onClick={() => setUsuarioEditando(u)}
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    className="usuarios-delete-btn"
                    onClick={() => eliminarUsuario(u.id)}
                  >
                    Eliminar
                  </button>
                </div>
              </div>
            ))
            )}
          </div>
        </div>
      </section>

      {usuarioEditando && (
        <EditarUsuario
          usuario={usuarioEditando}
          onCancel={() => setUsuarioEditando(null)}
          onSave={editarUsuario}
        />
      )}
    </div>
  );
}

function EditarUsuario({ usuario, onCancel, onSave }) {
  const [formEdit, setFormEdit] = useState({
    username: usuario.username || "",
    email: usuario.email || "",
    password: "",
  });

  const handleChange = (e) => {
    setFormEdit({
      ...formEdit,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(usuario.id, formEdit);
  };

  return (
    <section className="usuarios-card usuarios-edit-card">
      <h3>Editar usuario</h3>

      <form className="usuarios-form" onSubmit={handleSubmit}>
        <label>
          Usuario
          <input
            name="username"
            placeholder="Ingrese usuario"
            value={formEdit.username}
            onChange={handleChange}
            required
          />
        </label>

        <label>
          Email
          <input
            name="email"
            type="email"
            placeholder="Ingrese email"
            value={formEdit.email}
            onChange={handleChange}
            required
          />
        </label>

        <label>
          Password
          <input
            name="password"
            type="password"
            placeholder="Dejar vacío para mantener"
            value={formEdit.password}
            onChange={handleChange}
          />
        </label>

        <div className="usuarios-edit-role">
          <span>Rol</span>
          <strong>{formatearRolVisual(usuario.rol)}</strong>
        </div>

        <div className="usuarios-edit-actions">
          <button type="button" className="usuarios-cancel-btn" onClick={onCancel}>
            Cancelar
          </button>
          <button type="submit" className="usuarios-save-btn">
            Guardar cambios
          </button>
        </div>
      </form>
    </section>
  );
}
