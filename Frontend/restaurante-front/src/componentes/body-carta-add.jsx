import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import MainMenu from "./Main-menu";
import "../styles/AddProductos.css";
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import { authFetch } from "../api";
import ProductoVariantesEditor from "./ProductoVariantesEditor";

export default function AddProductos() {
  const navigate = useNavigate();
  const { slug } = useParams();

  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingCategorias, setLoadingCategorias] = useState(true);
  const [error, setError] = useState("");
  const [variantes, setVariantes] = useState([]);

  const [form, setForm] = useState({
    restaurante: "",
    categoria: "",
    nombre: "",
    precio: "",
    descripcion: "",
    condiciones: "",
    disponible: true,
    destacado: false,
    orden: 0,
    imagen: null,
    preview: null,
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleImageChange = (e) => {
    const file = e.target.files[0];

    if (file) {
      setForm((prev) => ({
        ...prev,
        imagen: file,
        preview: URL.createObjectURL(file),
      }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const nombres = variantes.map((variante) => variante.nombre.trim().toLowerCase());
    if (nombres.some((nombre) => !nombre) || new Set(nombres).size !== nombres.length) {
      setError("Cada variante debe tener un nombre único.");
      setLoading(false);
      return;
    }
    if (variantes.some((variante) => variante.precio === "" || Number(variante.precio) < 0)) {
      setError("Cada variante debe tener un precio válido, igual o mayor a 0.");
      setLoading(false);
      return;
    }

    try {
      const formData = new FormData();
      formData.append("categoria", form.categoria);
      formData.append("nombre", form.nombre);
      formData.append("precio", form.precio);
      formData.append("descripcion", form.descripcion);
      formData.append("condiciones", form.condiciones);
      formData.append("disponible", form.disponible);
      formData.append("destacado", form.destacado);
      formData.append("orden", form.orden);

      if (form.imagen) {
        formData.append("imagen", form.imagen);
      }

      const response = await authFetch("/mi-restaurante/productos/agregar/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("No se pudo guardar el producto");
      }

      const producto = await response.json();
      for (const variante of variantes) {
        const varianteResponse = await authFetch(`/mi-restaurante/productos/${producto.id}/variantes/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...variante,
            nombre: variante.nombre.trim(),
            precio: Number(variante.precio),
            orden: Number(variante.orden) || 0,
          }),
        });
        if (!varianteResponse.ok) throw new Error("No se pudo guardar una variante");
      }

      navigate(`/carta-productos/${slug}`);
    } catch {
      setError("Error al guardar el producto");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const cargarCategorias = async () => {
      try {
        setLoadingCategorias(true);
        const response = await authFetch("/mi-restaurante/");

        if (!response.ok) {
          throw new Error("Error al cargar categorías");
        }

        const data = await response.json();
        setCategorias(data.categorias);
        setForm((prev) => ({
          ...prev,
          restaurante: data.restaurante?.nombre_empresa || "",
        }));
      } catch {
        setError("No se pudieron cargar las categorías");
      } finally {
        setLoadingCategorias(false);
      }
    };

    cargarCategorias();
  }, []);

  return (
    <div className="body">
      <main className="container-fluid" id="main">
        <MainMenu />

        <section className="body-main">
          <header className="body-header">
            <div className="header-name-search">
              <h1>Agregar Producto</h1>
              {error && <div className="alert alert-danger">{error}</div>}
              {loadingCategorias && <p>Cargando categorías...</p>}
              <p className="p-header">Completa la información para agregar un nuevo producto a tu carta.</p>
            </div>

            <div className="div-seguimiento">
              <a href="">Inicio</a>
              <span>{" > "}</span>
              <a href="">Carta / Productos</a>
              <span>{" > "}</span>
              <a className="a-active" href="">
                Agregar productos
              </a>
            </div>
          </header>

          <form onSubmit={handleSubmit}>
            <div className="body-contenido1">
              <div className="contenido1">
                <div className="form">
                  <p className="info-header">
                    <span>
                      <i className="bi bi-file-earmark-text-fill"></i>
                    </span>{" "}
                    Información del producto
                  </p>

                  <div className="row g-3">
                    <div className="col-md-6">
                      <label className="form-label">Restaurante</label>
                      <input
                        type="text"
                        className="form-control"
                        name="restaurante"
                        value={form.restaurante}
                        disabled
                      />
                    </div>

                    <div className="col-md-6">
                      <label className="form-label">
                        Categoría <span className="text-danger">*</span>
                      </label>
                      <select
                        className="form-select"
                        name="categoria"
                        value={form.categoria}
                        onChange={handleChange}
                        disabled={loadingCategorias}
                        required
                      >
                        <option value="">Seleccionar categoría</option>

                        {loadingCategorias ? (
                          <option value="" disabled>
                            Cargando categorías...
                          </option>
                        ) : categorias.length === 0 ? (
                          <option value="" disabled>
                            No hay categorías disponibles
                          </option>
                        ) : (
                          categorias.map((cat) => (
                            <option key={cat.id} value={cat.id}>
                              {cat.nombre}
                            </option>
                          ))
                        )}
                      </select>
                    </div>

                    <div className="col-md-6">
                      <label className="form-label">
                        Nombre del producto <span className="text-danger">*</span>
                      </label>
                      <input
                        type="text"
                        className="form-control"
                        name="nombre"
                        placeholder="Ej: Lomo Saltado Clásico"
                        value={form.nombre}
                        onChange={handleChange}
                        required
                      />
                    </div>

                    <div className="col-md-6">
                      <label className="form-label">
                        Precio (CLP) <span className="text-danger">*</span>
                      </label>
                      <div className="input-group">
                        <span className="input-group-text">CLP</span>
                        <input
                          type="number"
                          className="form-control"
                          name="precio"
                          placeholder="Ej: 10990"
                          value={form.precio}
                          onChange={handleChange}
                          required
                        />
                      </div>
                    </div>

                    <div className="col-12">
                      <label className="form-label">Descripción</label>
                      <textarea
                        className="form-control"
                        name="descripcion"
                        rows="4"
                        placeholder="Describe los ingredientes y detalle del producto..."
                        value={form.descripcion}
                        onChange={handleChange}
                      ></textarea>
                    </div>

                    <div className="col-12">
                      <label className="form-label">Condiciones (opcional)</label>
                      <textarea
                        className="form-control"
                        name="condiciones"
                        rows="3"
                        placeholder="Ej: Picante a elección, etc..."
                        value={form.condiciones}
                        onChange={handleChange}
                      ></textarea>
                    </div>
                  </div>
                </div>

                <ProductoVariantesEditor variantes={variantes} onChange={setVariantes} />

                <div className="form mt-4" >
                  <p className="info-header">
                    <span>
                      <i className="bi bi-gear"></i>
                    </span>{" "}
                    Configuración del producto
                  </p>

                  <div className="row g-4" id="div-configuracion">
                    <div className="posicion-div">
                      <div className="col-md-6">
                        <div className="config-item">
                          <div className="div-text-configuracion-producto">
                            <label className="form-label d-block mb-1">Disponible</label>
                            <small>El producto estará visible para los clientes</small>
                          </div>

                          <div className="form-check form-switch mt-2">
                            <input
                              className="form-check-input"
                              type="checkbox"
                              name="disponible"
                              checked={form.disponible}
                              onChange={handleChange}
                            />
                          </div>
                        </div>
                      </div>

                      <div className="col-md-6">
                        <div className="config-item" id="config-item-1">
                          <div className="div-text-configuracion-producto">
                            <label className="form-label d-block mb-1">Destacado</label>
                            <small>Aparecerá en secciones destacadas</small>
                          </div>

                          <div className="form-check form-switch mt-2">
                            <input
                              className="form-check-input"
                              type="checkbox"
                              name="destacado"
                              checked={form.destacado}
                              onChange={handleChange}
                            />
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="posicion-div">
                      <div className="text-posicion">
                        <label className="form-label">Orden de la carta</label>
                        <p>Determina la posicion del producto en la lista</p>
                      </div>
                      <select
                        className="form-select"
                        name="orden"
                        value={form.orden}
                        onChange={handleChange}
                      >
                        <option value="0">0</option>
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                        <option value="5">5</option>
                      </select>
                    </div>
                    <div className="div-text-footer">
                       <small>El producto se mostrará en la carta según la categoría y el orden establecido.</small>
                    </div>
                   
                  </div>
                </div>
              </div>

              <div className="contenido2">
                <div className="form">
                  <p className="info-header">
                    <span>
                      <i className="bi bi-file-earmark-image"></i>
                    </span>{" "}
                    Imagen del producto
                  </p>

                  <label className="upload-box">
                    <input
                      type="file"
                      accept="image/*"
                      name="imagen"
                      onChange={handleImageChange}
                      hidden
                    />

                    <div className="upload-content">
                      <i className="bi bi-cloud-arrow-up fs-1"></i>
                      <p className="mb-1">Arrastra una imagen aquí o haz click en seleccionar</p>
                      <small>JPG, PNG o WebP. Máx. 5mb</small>
                    </div>
                  </label>

                  <div className="preview-box mt-3">
                    {form.preview ? (
                      <img
                        src={form.preview}
                        alt="Vista previa"
                        className="img-preview"
                      />
                    ) : (
                      <div className="preview-empty">Vista previa</div>
                    )}
                  </div>
                </div>

                <div className="form mt-4">
                  <p className="info-header">
                    <span>
                      <i className="bi bi-card-checklist"></i>
                    </span>{" "}
                    Vista y organización
                  </p>

                  <div className="view-info">
                    <div className="d-flex align-items-start gap-2 mb-3">
                      <i className="bi bi-check-square"></i>
                      <div>
                        <strong>Fecha de creación</strong>
                        <p className="mb-0">Se asignará automáticamente</p>
                      </div>
                    </div>

                    <div className="d-flex align-items-start gap-2">
                      <i className="bi bi-arrow-down-up"></i>
                      <div>
                        <strong>Según el orden establecido</strong>
                        <p className="mb-0">Se mostrará en la categoría seleccionada</p>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="btns-adds-cancel">
                  <button
                    type="button"
                    className="btn-cancel-productos"
                    onClick={() => navigate(-1)}
                  >
                    Cancelar
                  </button>

                  <button type="submit" className="btn-add-productos" disabled={loading}>
                    <i className="bi bi-floppy"></i>{" "}
                    {loading ? "Guardando..." : "Guardar producto"}
                  </button>
                </div>
              </div>
            </div>

            
          </form>
        </section>
      </main>
    </div>
  );
}
