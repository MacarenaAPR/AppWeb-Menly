import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { cocinaFetch, readJsonResponse } from "../api";
import "../styles/Cocina.css";

const POLLING_COCINA_MS = 10000;

const estadoLabels = {
  en_preparacion: "En preparacion",
  preparando: "En preparacion",
  listo: "Listo",
  entregado: "Entregado",
};

const origenLabels = {
  menly: "Menly",
  whatsapp: "WhatsApp",
  especial: "Especial",
};

const formatearHora = (valor) => {
  if (!valor) return "";
  return new Date(valor).toLocaleTimeString("es-CL", {
    hour: "2-digit",
    minute: "2-digit",
  });
};

const minutosTranscurridos = (valor) => {
  if (!valor) return 0;
  return Math.max(0, Math.floor((Date.now() - new Date(valor).getTime()) / 60000));
};

function ComandaCard({ comanda, onCambiarEstado, actualizando }) {
  const estado = comanda.estado === "preparando" ? "en_preparacion" : comanda.estado;
  const minutos = minutosTranscurridos(comanda.hora_creacion);
  const accion = estado === "listo"
    ? { estado: "entregado", texto: "Marcar entregado", icono: "bi-check2-circle" }
    : { estado: "listo", texto: "Marcar listo", icono: "bi-bell" };

  return (
    <article className={`cocina-comanda cocina-comanda-${estado}`}>
      <header>
        <div>
          <span className="cocina-origen">{origenLabels[comanda.tipo_origen] || comanda.tipo_origen}</span>
          <h2>Pedido #{comanda.numero}</h2>
        </div>
        <strong>{minutos <= 0 ? "Ahora" : `Hace ${minutos} min`}</strong>
      </header>

      <div className="cocina-meta">
        <span>{estadoLabels[estado] || estado}</span>
        <span>{formatearHora(comanda.hora_creacion)}</span>
        <span>{comanda.tipo_entrega_display || comanda.tipo_entrega}</span>
        {comanda.numero_mesa && <span>Mesa {comanda.numero_mesa}</span>}
      </div>

      {comanda.cliente_nombre && (
        <p className="cocina-cliente">{comanda.cliente_nombre}</p>
      )}

      <div className="cocina-items">
        {(comanda.items || []).map((item, index) => (
          <div key={`${item.nombre}-${index}`} className="cocina-item">
            <span>{item.cantidad}x {item.nombre}</span>
            {item.observaciones && <small>{item.observaciones}</small>}
          </div>
        ))}
      </div>

      {comanda.observaciones && (
        <p className="cocina-observacion">
          <strong>Observacion:</strong> {comanda.observaciones}
        </p>
      )}

      <button
        type="button"
        onClick={() => onCambiarEstado(comanda.id, accion.estado)}
        disabled={actualizando}
      >
        <i className={`bi ${accion.icono}`}></i>
        {actualizando ? "Actualizando..." : accion.texto}
      </button>
    </article>
  );
}

export default function PedidosCocina() {
  const navigate = useNavigate();
  const [restaurante, setRestaurante] = useState(null);
  const [comandas, setComandas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sesionInvalida, setSesionInvalida] = useState(false);
  const [ultimaActualizacion, setUltimaActualizacion] = useState(null);
  const [actualizandoId, setActualizandoId] = useState("");
  const [horaActual, setHoraActual] = useState(new Date());

  const cargarComandas = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true);
      setError("");
    }

    try {
      const response = await cocinaFetch("/cocina/comandas/");
      if (response.status === 401) {
        setSesionInvalida(true);
        setRestaurante(null);
        setComandas([]);
        setError("Sesion de cocina expirada o invalida.");
        return;
      }

      const data = await readJsonResponse(
        response,
        "/cocina/comandas/",
        "No se pudieron cargar las comandas."
      );
      setRestaurante(data.restaurante || null);
      setComandas(data.comandas || []);
      setUltimaActualizacion(new Date());
      setSesionInvalida(false);
      setError("");
    } catch (requestError) {
      if (!silent) {
        setError(requestError.message || "Sesion de cocina expirada.");
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarComandas();
  }, [cargarComandas]);

  useEffect(() => {
    if (sesionInvalida) return undefined;
    const intervalId = window.setInterval(() => {
      if (document.hidden) return;
      cargarComandas({ silent: true });
    }, POLLING_COCINA_MS);
    const relojId = window.setInterval(() => setHoraActual(new Date()), 30000);

    return () => {
      window.clearInterval(intervalId);
      window.clearInterval(relojId);
    };
  }, [cargarComandas, sesionInvalida]);

  const agrupadas = useMemo(() => ({
    en_preparacion: comandas.filter((comanda) => comanda.estado === "en_preparacion" || comanda.estado === "preparando"),
    listo: comandas.filter((comanda) => comanda.estado === "listo"),
  }), [comandas]);

  const cambiarEstado = async (id, estado) => {
    setActualizandoId(id);
    setError("");
    try {
      const response = await cocinaFetch(`/cocina/comandas/${encodeURIComponent(id)}/estado/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estado }),
      });
      await readJsonResponse(
        response,
        `/cocina/comandas/${id}/estado/`,
        "No se pudo actualizar la comanda."
      );
      await cargarComandas({ silent: true });
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar la comanda.");
    } finally {
      setActualizandoId("");
    }
  };

  const cerrarCocina = async () => {
    await cocinaFetch("/cocina/cerrar/", { method: "POST" }).catch(() => {});
    navigate("/", { replace: true });
  };

  if (loading) {
    return (
      <main className="cocina-page">
        <section className="cocina-auth-card">
          <span>Menly Cocina</span>
          <h1>Cargando comandas...</h1>
        </section>
      </main>
    );
  }

  if (sesionInvalida || (error && !restaurante)) {
    return (
      <main className="cocina-auth-page">
        <section className="cocina-auth-card">
          <span>Menly Cocina</span>
          <h1>Sesion no disponible</h1>
          <p>{error}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="cocina-page">
      <header className="cocina-header">
        <div>
          <span>Menly Cocina</span>
          <h1>{restaurante?.nombre_empresa || "Cocina"}</h1>
          <p>
            {horaActual.toLocaleDateString("es-CL", { dateStyle: "full" })} · {horaActual.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
        <div className="cocina-header-stats">
          <strong>{comandas.length}</strong>
          <span>comandas activas</span>
          <small>Actualizado {ultimaActualizacion ? formatearHora(ultimaActualizacion) : "--:--"}</small>
        </div>
        <button type="button" onClick={cerrarCocina}>
          <i className="bi bi-box-arrow-right"></i>
          Cerrar cocina
        </button>
      </header>

      {error && <p className="cocina-error">{error}</p>}

      <section className="cocina-board">
        <div className="cocina-column">
          <h2>En preparacion <span>{agrupadas.en_preparacion.length}</span></h2>
          {agrupadas.en_preparacion.length === 0 ? (
            <p className="cocina-empty">Sin comandas en preparacion.</p>
          ) : agrupadas.en_preparacion.map((comanda) => (
            <ComandaCard
              key={comanda.id}
              comanda={comanda}
              onCambiarEstado={cambiarEstado}
              actualizando={actualizandoId === comanda.id}
            />
          ))}
        </div>

        <div className="cocina-column cocina-column-listo">
          <h2>Listos <span>{agrupadas.listo.length}</span></h2>
          {agrupadas.listo.length === 0 ? (
            <p className="cocina-empty">Sin comandas listas.</p>
          ) : agrupadas.listo.map((comanda) => (
            <ComandaCard
              key={comanda.id}
              comanda={comanda}
              onCambiarEstado={cambiarEstado}
              actualizando={actualizandoId === comanda.id}
            />
          ))}
        </div>
      </section>
    </main>
  );
}
