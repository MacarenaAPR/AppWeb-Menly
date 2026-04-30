export default function Menu({ categorias }) {
  console.log("MENU:", categorias);

  if (!categorias || categorias.length === 0) {
    return <p>Cargando menú...</p>;
  }

  return (
    <section>
      {categorias.map((cat, index) => (
        <div key={index}>
          <h2>{cat.categoria}</h2>

          {cat.productos.map((producto, i) => (
            <div key={i}>
              <h3>{producto.nombre}</h3>
              <p>{producto.descripcion}</p>
              <p>${producto.precio}</p>
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}