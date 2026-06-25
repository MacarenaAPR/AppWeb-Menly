import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/home";
import SeguimientoPedidoPage from "./pages/SeguimientoPedidoPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/restaurantes/:slug" element={<Home />} />
        <Route path="/seguimiento/pedido/:trackingToken" element={<SeguimientoPedidoPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
