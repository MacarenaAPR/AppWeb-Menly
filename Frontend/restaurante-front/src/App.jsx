

import './App.css'
import { lazy, Suspense } from 'react';
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
import PedidosCocina from './pages/PedidosCocina'
import CocinaActivar from './pages/CocinaActivar'
import ConfiguracionRestaurante from './pages/Configuracion'
import SaberMas from './pages/SaberMas'
import Planes from './pages/Planes'
import RequireRole from './componentes/RequireRole'
import Footer from './componentes/Footer'
import SessionExpiryModal from './componentes/SessionExpiryModal'
import { useLocation } from 'react-router-dom';
import useAdminInactivity from './hooks/useAdminInactivity';

const MetricasDashboard = lazy(() => import('./pages/Metricas'));


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

function AppContent() {
  const location = useLocation();
  const esRutaCocina = location.pathname.startsWith("/pedidos-cocina");
  const adminSession = useAdminInactivity(location.pathname);

  return (
      <div className={`app-shell ${esRutaCocina ? "app-shell-cocina" : ""}`}>
        <Routes>
          <Route path="/pedidos-cocina/activar/:token" element={<CocinaActivar />} />
          <Route path="/pedidos-cocina" element={<PedidosCocina />} />
          <Route path="/dashboard/:slug/configuracion" element={
            <RequireRole roles={["dueno", "admin"]}>
              <ConfiguracionRestaurante />
            </RequireRole>
          }/>
          <Route path="/dashboard/:slug/reservas" element={<ReservasDashboard />} />
          <Route path="/dashboard/:slug/solicitudes-especiales" element={<SolicitudesEspecialesDashboard />} />
          <Route path="/dashboard/:slug/pedidos" element={<PedidosDashboard />} />
          <Route path="/dashboard/:slug/metricas" element={
            <RequireRole roles={["dueno", "admin"]}>
              <Suspense fallback={null}>
                <MetricasDashboard />
              </Suspense>
            </RequireRole>
          } />
          <Route path="/carta-add/:slug" element={
            <RequireRole roles={["dueno", "admin"]}>
              <AddProductos />
            </RequireRole>
          } />
          <Route path="/saber-mas" element={<SaberMas />} />
          <Route path="/planes" element={<Planes />} />
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
        {!esRutaCocina && (
          <SessionExpiryModal
            warning={adminSession.warning}
            onKeepSession={adminSession.keepSession}
            onLogout={adminSession.closeSession}
          />
        )}
        {!esRutaCocina && <Footer />}
      </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
