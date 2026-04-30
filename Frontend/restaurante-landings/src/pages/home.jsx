import { useEffect, useState } from "react";

const BASE_URL = "http://127.0.0.1:8000/api";

export default function App() {
  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(true);

  const slug = "la-mechada-real";

  useEffect(() => {
    const fetchMenu = async () => {
      try {
        const res = await fetch(`${BASE_URL}/menu/${slug}/`);
        const data = await res.json();

        console.log("DATA:", data);
        setCategorias(data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };

    fetchMenu();
  }, []);

  if (loading) return <p>Cargando...</p>;

  return (
    <div style={{ padding: "20px", color: "white", background: "#111" }}>
      <h1>La Mechada Real</h1>

      {/* MENÚ */}
      {categorias.map((cat, index) => (
        <div key={index} style={{ marginBottom: "30px" }}>
          <h2>{cat.categoria}</h2>

          {cat.productos.length === 0 ? (
            <p>No hay productos</p>
          ) : (
            cat.productos.map((p, i) => (
              <div
                key={i}
                onClick={() => handleClickProducto(p.id)}
                style={{
                  border: "1px solid #333",
                  padding: "10px",
                  marginBottom: "10px",
                  cursor: "pointer",
                }}
              >
                <p>{p.nombre}</p>
                <p>${p.precio}</p>
              </div>
            ))
          )}
        </div>
      ))}

      {/* FORM RESERVA */}
      <h2>Reservar</h2>

      <form onSubmit={handleReserva}>
        <input name="nombre_cliente" placeholder="Nombre" required />
        <input name="telefono" placeholder="Teléfono" required />
        <input name="email" type="email" placeholder="Email" />
        <input name="fecha" type="date" required />
        <input name="hora" type="time" required />
        <input name="cantidad_personas" type="number" min="1" placeholder="Personas" required />
        <textarea name="mensaje" placeholder="Mensaje opcional"></textarea>

        <button type="submit">Reservar</button>
      </form>
    </div>
  );

  // 🔥 CLICK PRODUCTO
  async function handleClickProducto(id) {
    try {
      await fetch(`${BASE_URL}/productos/${id}/click/`, {
        method: "POST",
      });
    } catch (error) {
      console.error("Error click", error);
    }
  }

  // 📩 RESERVA
  async function handleReserva(e) {
    e.preventDefault();

    const formData = new FormData(e.target);

    const data = {
      nombre_cliente: formData.get("nombre_cliente"),
      telefono: formData.get("telefono"),
      email: formData.get("email"),
      fecha: formData.get("fecha"),
      hora: formData.get("hora"),
      cantidad_personas: Number(formData.get("cantidad_personas")),
      mensaje: formData.get("mensaje") || "",
    };

    console.log("ENVIANDO:", data);

    const res = await fetch(`${BASE_URL}/reservas/${slug}/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    const result = await res.json();
    console.log("RESPUESTA:", result);

    if (!res.ok) {
      alert(result.error || JSON.stringify(result));
      return;
    }

    alert(result.message);
    e.target.reset();
  }
}