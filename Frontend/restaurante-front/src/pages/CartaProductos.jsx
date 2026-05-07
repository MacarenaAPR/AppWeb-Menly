import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/dashboard.css";
import "../styles/CartaProductos.css";
import "../styles/styles-default.css";
import CartaProducto from "../componentes/body-carta-productos";
import MainMenu from "../componentes/Main-menu";

export default function CartaProductos() {

  return (
    <div className="body">
      <main className="container-fluid" id="main">
        <MainMenu />
        <CartaProducto/>
      </main>
    </div>
  );
}
