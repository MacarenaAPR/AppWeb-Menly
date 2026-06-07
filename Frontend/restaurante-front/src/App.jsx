

import './App.css'
import Dashboard from "./pages/Dashboard";
import CartaProductos from "./pages/CartaProductos";
import Login from "./pages/login";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AddProductos from "./componentes/body-carta-add";
import EditProductos from './componentes/body-carta-upload';
import Historial from './pages/Historial'
import ReservasDashboard from './pages/Reserva'
import SolicitudesEspecialesDashboard from './pages/SolicitudesEspeciales'
import PedidosDashboard from './pages/Pedidos'
import MetricasDashboard from './pages/Metricas'
import ConfiguracionRestaurante from './pages/Configuracion'
import RequireRole from './componentes/RequireRole'
import Footer from './componentes/Footer'


function MetricasPlaceholder() {
  return (
    <main className="dashboard">
      <section className="dashboard-header">
        <div>
          <p>Menly</p>
          <h1>Métricas</h1>
        </div>
      </section>
      <section className="dashboard-section">
        <p>El módulo de métricas está activo. La página se implementará próximamente.</p>
      </section>
    </main>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Routes>
          <Route path="/dashboard/:slug/configuracion" element={
            <RequireRole roles={["dueno", "admin"]}>
              <ConfiguracionRestaurante />
            </RequireRole>
          }/>
          <Route path="/dashboard/:slug/reservas" element={<ReservasDashboard />} />
          <Route path="/dashboard/:slug/solicitudes-especiales" element={<SolicitudesEspecialesDashboard />} />
          <Route path="/dashboard/:slug/pedidos" element={<PedidosDashboard />} />
          <Route path="/dashboard/:slug/metricas" element={<MetricasDashboard />} />
          <Route path="/carta-add/:slug" element={
            <RequireRole roles={["dueno", "admin"]}>
              <AddProductos />
            </RequireRole>
          } />
          <Route path="/" element={<Login />} />
          <Route path="/dashboard/:slug" element={<Dashboard />} />
          <Route path="/carta-productos/:slug" element={<CartaProductos />} />
          <Route path="/carta-productos/:slug/editar/:id" element={
            <RequireRole roles={["dueno", "admin"]}>
              <EditProductos />
            </RequireRole>
          } />
          <Route path="/historial" element={
            <RequireRole roles={["dueno"]}>
              <Historial />
            </RequireRole>
          } />
        </Routes>
        <Footer />
      </div>
    </BrowserRouter>
  );
}

export default App;
