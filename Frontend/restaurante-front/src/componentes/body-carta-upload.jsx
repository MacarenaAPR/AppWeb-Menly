import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import MainMenu from "./Main-menu";
import "../styles/AddProductos.css";
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import { authFetch } from "../api";


export default function EditProductos() {
  const navigate = useNavigate();
  const { slug, id } = useParams();
  const [productos, setProductos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingDatos, setLoadingDatos] = useState(true);
  const [error, setError] = useState("");
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
    fecha_creacion: "",
  });
  const productosCategoria = productos.filter((prod) => {
    const categoriaProducto =
      typeof prod.categoria === "object" && prod.categoria !== null
        ? String(prod.categoria.id)
        : String(categorias.find(cat => String(cat.nombre) === String(prod.categoria))?.id || "");

    return categoriaProducto === String(form.categoria);
  });
  const totalOrdenes = Math.max(productosCategoria.length, form.orden);
  
  useEffect(() => {
    const cargarDatos = async () => {
      try {
        setLoadingDatos(true);
        const response = await authFetch("/mi-restaurante/");

        if (!response.ok) {
          throw new Error("Error al cargar datos");
        }

        const data = await response.json();

        setCategorias(data.categorias);
        setProductos(data.productos);

        const producto = data.productos.find((p) => p.id === Number(id));

        if (!producto) {
          setError("Producto no encontrado");
          navigate(`/carta-productos/${slug}`);
          return;
        }
        const categoriaActual = data.categorias.find(
        (cat) => cat.id === producto.categoria?.id || cat.nombre === producto.categoria
        );
        setForm({
          restaurante: data.restaurante.nombre_empresa,
          categoria: categoriaActual ? String(categoriaActual.id) : "",
          nombre: producto.nombre || "",
          precio: producto.precio || "",
          descripcion: producto.descripcion || "",
          condiciones: producto.condiciones || "",
          disponible: producto.disponible ?? true,
          destacado: producto.destacado ?? false,
          orden: producto.orden || 0,
          imagen: null,
          preview: producto.imagen || null,
          fecha_creacion: producto.fecha_creacion,
        });
      } catch {
        setError("No se pudieron cargar los datos del producto");
      } finally {
        setLoadingDatos(false);
      }
    };

    cargarDatos();
  }, [id, slug, navigate]);

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

    try {
      const formData = new FormData();
      formData.append("categoria", form.categoria);
      formData.append("nombre", form.nombre);
      formData.append("precio", form.precio);
      formData.append("descripcion", form.descripcion);
      formData.append("condiciones", form.condiciones);
      formData.append("disponible", form.disponible ? "true" : "false");
      formData.append("destacado", form.destacado ? "true" : "false");
      formData.append("orden", form.orden);

      if (form.imagen) {
        formData.append("imagen", form.imagen);
      }

      const response = await authFetch(`/mi-restaurante/productos/${id}/actualizar/`, {
        method: "PATCH",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("No se pudo actualizar");
      }

      navigate(`/carta-productos/${slug}`);
    } catch {
      setError("Error al actualizar el producto");
    } finally {
      setLoading(false);
    }
  };
  const formatearFecha = (fecha) => {
    if (!fecha) return "";

    return new Date(fecha).toLocaleDateString("es-CL", {
        weekday: "long",   // 👈 AQUÍ
        day: "2-digit",
        month: "long",
        year: "numeric",
    });
    };
  const productosOrdenadosGlobal = [...productos].sort((a, b) => a.orden - b.orden);

  const ordenGlobal =
    productosOrdenadosGlobal.findIndex(
        (producto) => producto.id === Number(id)
    ) + 1;


  return (
    <div className="body">
      <main className="container-fluid" id="main">
        <MainMenu />

        <section className="body-main">
          <header className="body-header">
            <div className="header-name-search">
                <h1>Editar Producto</h1>
                {error && <div className="alert alert-danger">{error}</div>}
                {loadingDatos && <p>Cargando producto...</p>}
                <p className="p-header">Actualiza la información del producto de tu carta.</p>
            </div>

            <div className="div-seguimiento">
              <a href="">Inicio</a>
              <span>{" > "}</span>
              <a href="">Carta / Productos</a>
              <span>{" > "}</span>
              <a className="a-active" href=""> Editar producto</a>
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
                        disabled={loadingDatos}
                        required
                        >
                        <option value="">Seleccionar categoría</option>

                        {loadingDatos ? (
                          <option value="" disabled>
                            Cargando categorías...
                          </option>
                        ) : categorias.length === 0 ? (
                          <option value="" disabled>
                            No hay categorías disponibles
                          </option>
                        ) : (
                          categorias.map((cat) => (
                            <option key={cat.id} value={String(cat.id)}>
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
                        {Array.from({ length: totalOrdenes }, (_, i) => i + 1).map((num) => (
                            <option key={num} value={num}>
                            {num}
                            </option>
                        ))}
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
                        <p className="mb-0">
                        {form.fecha_creacion
                            ? formatearFecha(form.fecha_creacion)
                            : "Cargando..."}
                        </p>
                      </div>
                    </div>

                    <div className="d-flex align-items-start gap-2">
                      <i className="bi bi-arrow-down-up"></i>
                      <div>
                        <strong>
                            Orden {form.orden} en la categoría seleccionada
                        </strong>

                        <p className="mb-0">
                            Producto #{ordenGlobal} entre todos los productos del restaurante
                        </p>
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
                    {loading ? "Actualizando..." : "Actualizar producto"}
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
