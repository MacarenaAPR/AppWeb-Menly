import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch } from "../Services/api";
import "../styles/seguimiento-pedido.css";

const TRACKING_REFRESH_MS = 20000;

const ESTADOS = [
  "recibido",
  "pendiente_confirmacion",
  "confirmado",
  "en_preparacion",
  "en_delivery",
  "listo",
  "entregado",
];

const ESTADO_LABELS = {
  recibido: "Pedido recibido",
  pendiente_confirmacion: "Pendiente de confirmacion",
  confirmado: "Confirmado",
  en_preparacion: "En preparacion",
  en_delivery: "En camino",
  listo: "Listo",
  entregado: "Entregado",
  cancelado: "Cancelado",
};

const formatearMoneda = (valor) =>
  new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(Number(valor || 0));

const formatearFecha = (valor) => {
  if (!valor) return "Sin actualizacion";
  return new Date(valor).toLocaleString("es-CL", {
    dateStyle: "medium",
    timeStyle: "short",
  });
};

export default function SeguimientoPedidoPage() {
  const { trackingToken } = useParams();
  const [pedido, setPedido] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let activo = true;
    let intervalId;

    const cargarPedido = async ({ silent = false } = {}) => {
      if (!silent) {
        setLoading(true);
        setError("");
      }

      try {
        const data = await apiFetch(`/public/pedidos/seguimiento/${trackingToken}/`, {
          retries: 0,
        });
        if (activo) {
          setPedido(data);
          setError("");
        }
      } catch (requestError) {
        if (!activo) return;
        if (silent) {
          return;
        }
        if (requestError?.status === 404) {
          setError("No encontramos este pedido o el enlace no es valido.");
        } else {
          setError("No pudimos cargar el seguimiento. Intenta nuevamente.");
        }
      } finally {
        if (activo && !silent) setLoading(false);
      }
    };

    cargarPedido();
    intervalId = window.setInterval(() => {
      cargarPedido({ silent: true });
    }, TRACKING_REFRESH_MS);

    return () => {
      activo = false;
      window.clearInterval(intervalId);
    };
  }, [trackingToken]);

  const progreso = useMemo(() => {
    if (!pedido || pedido.estado === "cancelado") return 0;
    const indice = ESTADOS.indexOf(pedido.estado);
    if (indice < 0) return 0;
    return Math.round(((indice + 1) / ESTADOS.length) * 100);
  }, [pedido]);

  if (loading) {
    return (
      <main className="tracking-page">
        <section className="tracking-card tracking-state-card">
          <span className="tracking-kicker">Menly</span>
          <h1>Cargando seguimiento...</h1>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="tracking-page">
        <section className="tracking-card tracking-state-card">
          <span className="tracking-kicker">Seguimiento de pedido</span>
          <h1>{error}</h1>
          <p>Revisa que el enlace este completo o consulta directamente con el restaurante.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="tracking-page">
      <section className="tracking-card">
        <header className="tracking-header">
          <div>
            <span className="tracking-kicker">{pedido.restaurante_nombre}</span>
            <h1>Pedido #{pedido.numero_pedido}</h1>
          </div>
          <span className={`tracking-status tracking-status-${pedido.estado}`}>
            {ESTADO_LABELS[pedido.estado] || pedido.estado_display || pedido.estado}
          </span>
        </header>

        <div className="tracking-progress" aria-label="Progreso del pedido">
          <span style={{ width: `${progreso}%` }} />
        </div>

        <dl className="tracking-summary">
          <div>
            <dt>Ultima actualizacion</dt>
            <dd>{formatearFecha(pedido.fecha_actualizacion_estado)}</dd>
          </div>
          <div>
            <dt>Entrega</dt>
            <dd>{pedido.tipo_entrega_display || pedido.tipo_entrega}</dd>
          </div>
          <div>
            <dt>Total</dt>
            <dd>{formatearMoneda(pedido.total)}</dd>
          </div>
        </dl>

        <section className="tracking-items">
          <h2>Productos</h2>
          {(pedido.items || []).map((item, index) => (
            <div className="tracking-item" key={`${item.nombre}-${index}`}>
              <span>{item.cantidad} x {item.nombre}</span>
              <strong>{formatearMoneda(item.subtotal)}</strong>
            </div>
          ))}
        </section>

        {pedido.observaciones_cliente && (
          <p className="tracking-note">{pedido.observaciones_cliente}</p>
        )}

        {pedido.whatsapp_contacto_url && (
          <a
            className="tracking-whatsapp"
            href={pedido.whatsapp_contacto_url}
            target="_blank"
            rel="noreferrer"
          >
            Consultar por WhatsApp
          </a>
        )}
      </section>
    </main>
  );
}
