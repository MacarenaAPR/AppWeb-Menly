import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Chart from "react-apexcharts";
import jsPDF from "jspdf";

import MainMenu from "../componentes/Main-menu";
import { authFetch } from "../api";
import "../styles/Metricas.css";

const planFallback = { id: null, nombre: "Básico", slug: "basico" };

const formatearMoneda = (valor) =>
  new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(Number(valor || 0));

function MetricCard({ icon, label, value, hint }) {
  return (
    <article className="metricas-card">
      <div className="metricas-card-icon"><i className={icon}></i></div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {hint && <small>{hint}</small>}
      </div>
    </article>
  );
}

function ResumenMensualChart({ whatsappMes, especialesMes }) {
  const maximo = Math.max(whatsappMes, especialesMes, 1);

  return (
    <section className="metricas-panel">
      <div className="metricas-panel-header">
        <div>
          <span>Resumen mensual</span>
          <h2>Pedidos del mes</h2>
        </div>
      </div>
      <div className="metricas-bars">
        <div className="metricas-bar-row">
          <span>WhatsApp</span>
          <div><i style={{ width: `${(whatsappMes / maximo) * 100}%` }} /></div>
          <strong>{whatsappMes}</strong>
        </div>
        <div className="metricas-bar-row">
          <span>Especiales</span>
          <div><i style={{ width: `${(especialesMes / maximo) * 100}%` }} /></div>
          <strong>{especialesMes}</strong>
        </div>
      </div>
    </section>
  );
}

function MetricasBasicas({ metricas }) {
  const ventaMensual = metricas?.whatsapp?.venta_mensual_total || 0;
  const pedidosMes = metricas?.whatsapp?.pedidos_mes || 0;
  const pedidosEspecialesMes = metricas?.especiales?.pedidos_mes || 0;

  return (
    <>
      <section className="metricas-grid">
        <MetricCard icon="bi bi-currency-dollar" label="Venta mensual total" value={formatearMoneda(ventaMensual)} />
        <MetricCard icon="bi bi-bag-check" label="Pedidos del mes" value={pedidosMes} />
        <MetricCard icon="bi bi-calendar-heart" label="Pedidos especiales del mes" value={pedidosEspecialesMes} />
      </section>
      <ResumenMensualChart whatsappMes={pedidosMes} especialesMes={pedidosEspecialesMes} />
      <section className="metricas-upgrade">
        <i className="bi bi-stars"></i>
        <p>Tu plan actual es Básico. Accede a más métricas con Pro.</p>
      </section>
    </>
  );
}

function ProductosMasVendidos({ productos }) {
  return (
    <section className="metricas-panel">
      <div className="metricas-panel-header">
        <div>
          <span>Productos</span>
          <h2>Productos más vendidos</h2>
        </div>
      </div>
      <div className="metricas-table-lite">
        {productos.length === 0 ? (
          <p className="metricas-empty">Aún no hay datos suficientes.</p>
        ) : (
          productos.slice(0, 5).map((producto, index) => (
            <div key={producto.id || producto.nombre}>
              <span>{index + 1}</span>
              <strong>{producto.nombre}</strong>
              <small>{producto.clicks ?? producto.cantidad ?? 0} interacciones</small>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function ReporteMensualModal({ reporte, loading, error, onClose }) {
  const descargarPdf = () => {
    if (!reporte) return;

    const pdf = new jsPDF("p", "mm", "a4");
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const margin = 16;
    const contentWidth = pageWidth - margin * 2;
    const footerY = pageHeight - 12;
    const fechaDescarga = new Date().toLocaleDateString("es-CL", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    let y = 18;

    const productosReporte = [
      ...(Array.isArray(reporte.productos_vendidos) ? reporte.productos_vendidos : []),
      ...(Array.isArray(reporte.resumen_productos) ? reporte.resumen_productos : []),
      ...(Array.isArray(reporte.productos) ? reporte.productos : []),
    ];

    if (productosReporte.length === 0) {
      [reporte.producto_mas_vendido, reporte.producto_menos_vendido]
        .filter(Boolean)
        .forEach((producto) => {
          if (!productosReporte.some((item) => item.nombre === producto.nombre)) {
            productosReporte.push(producto);
          }
        });
    }

    const addFooter = () => {
      pdf.setFontSize(9);
      pdf.setTextColor(110, 120, 135);
      pdf.text("Generado por Menly", margin, footerY);
      pdf.text(`Fecha de descarga: ${fechaDescarga}`, pageWidth - margin, footerY, { align: "right" });
    };

    const ensureSpace = (height = 10) => {
      if (y + height <= footerY - 8) return;
      addFooter();
      pdf.addPage();
      y = 18;
    };

    const addSectionTitle = (title) => {
      ensureSpace(12);
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(14);
      pdf.setTextColor(20, 28, 38);
      pdf.text(title, margin, y);
      y += 8;
    };

    const addKeyValue = (label, value, x, rowY, width = 82) => {
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9);
      pdf.setTextColor(90, 100, 115);
      pdf.text(label, x, rowY);
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(11);
      pdf.setTextColor(20, 28, 38);
      const text = pdf.splitTextToSize(String(value ?? "Sin datos"), width);
      pdf.text(text, x, rowY + 6);
    };

    const addTable = (headers, rows, widths) => {
      const rowHeight = 8;
      const drawHeader = () => {
        ensureSpace(rowHeight + 2);
        pdf.setFillColor(248, 118, 29);
        pdf.rect(margin, y, contentWidth, rowHeight, "F");
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(9);
        pdf.setTextColor(255, 255, 255);
        let x = margin + 3;
        headers.forEach((header, index) => {
          pdf.text(header, x, y + 5.5);
          x += widths[index];
        });
        y += rowHeight;
      };

      drawHeader();
      rows.forEach((row, rowIndex) => {
        ensureSpace(rowHeight + 2);
        if (y < 24) drawHeader();

        pdf.setFillColor(rowIndex % 2 === 0 ? 248 : 251, rowIndex % 2 === 0 ? 250 : 252, rowIndex % 2 === 0 ? 252 : 253);
        pdf.rect(margin, y, contentWidth, rowHeight, "F");
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(9);
        pdf.setTextColor(32, 40, 52);

        let x = margin + 3;
        row.forEach((cell, index) => {
          const cellText = pdf.splitTextToSize(String(cell ?? "-"), widths[index] - 6);
          pdf.text(cellText.slice(0, 1), x, y + 5.5);
          x += widths[index];
        });
        y += rowHeight;
      });
      y += 6;
    };

    pdf.setFillColor(255, 255, 255);
    pdf.rect(0, 0, pageWidth, pageHeight, "F");
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(22);
    pdf.setTextColor(20, 28, 38);
    pdf.text("Reporte mensual Menly", margin, y);
    y += 9;
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(11);
    pdf.setTextColor(90, 100, 115);
    pdf.text(`Mes: ${reporte.mes || "Mes actual"}`, margin, y);
    y += 12;

    ensureSpace(44);
    addKeyValue("Venta mensual total", formatearMoneda(reporte.venta_total), margin, y);
    addKeyValue("Pedidos totales", reporte.pedidos_total ?? 0, margin + 94, y);
    y += 18;
    addKeyValue("Pedidos cancelados", reporte.pedidos_cancelados ?? 0, margin, y);
    addKeyValue("Día de mayor venta", `Día ${reporte.dia_mayor_venta?.dia || "-"} · ${formatearMoneda(reporte.dia_mayor_venta?.total)}`, margin + 94, y);
    y += 18;
    addKeyValue("Día de menor venta", `Día ${reporte.dia_menor_venta?.dia || "-"} · ${formatearMoneda(reporte.dia_menor_venta?.total)}`, margin, y);
    addKeyValue("Producto más vendido", productoTexto(reporte.producto_mas_vendido), margin + 94, y);
    y += 18;
    addKeyValue("Producto menos vendido", productoTexto(reporte.producto_menos_vendido), margin, y);
    y += 16;

    addSectionTitle("Ventas diarias");
    addTable(
      ["Día", "Total vendido"],
      (reporte.venta_diaria || []).map((item) => [
        item.dia,
        formatearMoneda(item.total),
      ]),
      [42, contentWidth - 42],
    );

    addSectionTitle("Resumen de productos");
    addTable(
      ["Producto", "Cantidad", "Total vendido"],
      productosReporte.length > 0
        ? productosReporte.map((producto) => [
            producto.nombre || "Sin datos",
            producto.cantidad ?? 0,
            producto.total_vendido != null ? formatearMoneda(producto.total_vendido) : "-",
          ])
        : [["Sin datos", "-", "-"]],
      [contentWidth - 78, 34, 44],
    );

    const totalPages = pdf.getNumberOfPages();
    for (let page = 1; page <= totalPages; page += 1) {
      pdf.setPage(page);
      addFooter();
    }

    pdf.save(`reporte-mensual-menly-${reporte.mes}.pdf`);
  };

  const productoTexto = (producto) =>
    producto ? `${producto.nombre} (${producto.cantidad})` : "Sin datos";

  const ventaDiaria = reporte?.venta_diaria || [];
  const chartOptions = useMemo(() => ({
    chart: {
      type: "bar",
      background: "transparent",
      toolbar: { show: false },
      animations: {
        enabled: true,
        easing: "easeinout",
        speed: 650,
      },
      foreColor: "#94a3b8",
    },
    theme: { mode: "dark" },
    colors: ["#f8761d"],
    fill: {
      type: "gradient",
      gradient: {
        shade: "dark",
        type: "vertical",
        gradientToColors: ["#ffb06a"],
        opacityFrom: 1,
        opacityTo: 0.88,
        stops: [0, 100],
      },
    },
    plotOptions: {
      bar: {
        borderRadius: 6,
        columnWidth: "62%",
        dataLabels: { position: "top" },
      },
    },
    dataLabels: {
      enabled: true,
      offsetY: -18,
      formatter: (value) => (Number(value) > 0 ? `$${Number(value).toLocaleString("es-CL")}` : ""),
      style: {
        colors: ["#e2e8f0"],
        fontSize: "10px",
        fontWeight: 800,
      },
    },
    grid: {
      borderColor: "#172535",
      strokeDashArray: 4,
      xaxis: { lines: { show: false } },
    },
    xaxis: {
      categories: ventaDiaria.map((item) => String(item.dia)),
      labels: { style: { colors: "#94a3b8" } },
      axisBorder: { color: "#1e2d3d" },
      axisTicks: { color: "#1e2d3d" },
      title: {
        text: "Día del mes",
        style: { color: "#94a3b8", fontWeight: 700 },
      },
    },
    yaxis: {
      labels: {
        formatter: (value) => `$${Number(value).toLocaleString("es-CL")}`,
        style: { colors: "#94a3b8" },
      },
      title: {
        text: "Ventas",
        style: { color: "#94a3b8", fontWeight: 700 },
      },
    },
    tooltip: {
      theme: "dark",
      x: {
        formatter: (value) => `Día ${value}`,
      },
      y: {
        formatter: (value) => formatearMoneda(value),
        title: { formatter: () => "Venta" },
      },
    },
    responsive: [
      {
        breakpoint: 768,
        options: {
          plotOptions: {
            bar: { columnWidth: "76%" },
          },
          dataLabels: { enabled: false },
        },
      },
    ],
  }), [ventaDiaria]);

  const chartSeries = useMemo(() => ([
    {
      name: "Venta",
      data: ventaDiaria.map((item) => Number(item.total || 0)),
    },
  ]), [ventaDiaria]);

  return (
    <div className="metricas-modal-backdrop" role="dialog" aria-modal="true">
      <section className="metricas-modal">
        <button className="metricas-modal-close" type="button" onClick={onClose} aria-label="Cerrar">
          <i className="bi bi-x-lg"></i>
        </button>

        <header className="metricas-modal-header">
          <div>
            <span>Reporte mensual</span>
            <h2>{reporte?.mes || "Mes actual"}</h2>
          </div>
          {reporte && (
            <button className="metricas-report-btn" type="button" onClick={descargarPdf}>
              <i className="bi bi-download"></i>
              Descargar PDF
            </button>
          )}
        </header>

        {loading ? (
          <p className="metricas-empty">Cargando reporte mensual...</p>
        ) : error ? (
          <p className="metricas-error">{error}</p>
        ) : reporte ? (
          <>
            <section className="metricas-reporte-grid">
              <MetricCard icon="bi bi-currency-dollar" label="Venta mensual" value={formatearMoneda(reporte.venta_total)} />
              <MetricCard icon="bi bi-graph-up-arrow" label="Día mayor venta" value={`Día ${reporte.dia_mayor_venta?.dia || "-"}`} hint={formatearMoneda(reporte.dia_mayor_venta?.total)} />
              <MetricCard icon="bi bi-graph-down-arrow" label="Día menor venta" value={`Día ${reporte.dia_menor_venta?.dia || "-"}`} hint={formatearMoneda(reporte.dia_menor_venta?.total)} />
              <MetricCard icon="bi bi-bag-check" label="Pedidos totales" value={reporte.pedidos_total} />
              <MetricCard icon="bi bi-x-circle" label="Cancelados" value={reporte.pedidos_cancelados} />
              <MetricCard icon="bi bi-trophy" label="Más vendido" value={productoTexto(reporte.producto_mas_vendido)} />
              <MetricCard icon="bi bi-box" label="Menos vendido" value={productoTexto(reporte.producto_menos_vendido)} />
            </section>

            <section className="metricas-panel metricas-chart-panel">
              <div className="metricas-panel-header">
                <div>
                  <span>Venta diaria</span>
                  <h2>Días del mes</h2>
                </div>
              </div>
              <div className="metricas-chart-wrap">
                <Chart options={chartOptions} series={chartSeries} type="bar" height={320} />
              </div>
            </section>

            <section className="metricas-analisis-panel">
              <div>
                <span>Día de mayor venta</span>
                <strong>Día {reporte.dia_mayor_venta?.dia || "-"}</strong>
                <small>{formatearMoneda(reporte.dia_mayor_venta?.total)}</small>
              </div>
              <div>
                <span>Día de menor venta</span>
                <strong>Día {reporte.dia_menor_venta?.dia || "-"}</strong>
                <small>{formatearMoneda(reporte.dia_menor_venta?.total)}</small>
              </div>
              <div>
                <span>Producto más vendido</span>
                <strong>{reporte.producto_mas_vendido?.nombre || "Sin datos"}</strong>
                <small>{reporte.producto_mas_vendido?.cantidad || 0} unidades</small>
              </div>
              <div>
                <span>Producto menos vendido</span>
                <strong>{reporte.producto_menos_vendido?.nombre || "Sin datos"}</strong>
                <small>{reporte.producto_menos_vendido?.cantidad || 0} unidades</small>
              </div>
            </section>
          </>
        ) : null}
      </section>
    </div>
  );
}

function MetricasPro({ metricas, productos, onOpenReporte }) {
  const productoDia = metricas?.whatsapp?.producto_mas_vendido_dia;
  const productoMes = metricas?.whatsapp?.producto_mas_vendido_mes;

  return (
    <>
      <section className="metricas-grid">
        <MetricCard icon="bi bi-eye" label="Visitas" value={metricas?.visitas?.clicks_productos_total || 0} hint="Clicks en productos" />
        <MetricCard icon="bi bi-bag-check" label="Pedidos del mes" value={metricas?.whatsapp?.pedidos_mes || 0} />
        <MetricCard icon="bi bi-calendar2-check" label="Reservas del mes" value={metricas?.reservas?.reservas_mes || 0} />
        <MetricCard icon="bi bi-x-circle" label="Pedidos cancelados" value={(metricas?.whatsapp?.pedidos_cancelados || 0) + (metricas?.especiales?.pedidos_cancelados || 0)} />
      </section>
      <section className="metricas-grid">
        <MetricCard icon="bi bi-cash-stack" label="Venta diaria" value={formatearMoneda(metricas?.whatsapp?.venta_diaria_total)} />
        <MetricCard icon="bi bi-graph-up-arrow" label="Venta semanal" value={formatearMoneda(metricas?.whatsapp?.venta_semanal_total)} />
        <MetricCard icon="bi bi-calendar3" label="Venta mensual" value={formatearMoneda(metricas?.whatsapp?.venta_mensual_total)} />
      </section>
      <section className="metricas-two-columns">
        <ProductosMasVendidos productos={productos} />
        <section className="metricas-panel">
          <div className="metricas-panel-header">
            <div>
              <span>Reportes</span>
              <h2>Resumen Pro</h2>
            </div>
          </div>
          <div className="metricas-report-list">
            <p><strong>Producto del día:</strong> {productoDia?.nombre || "Sin datos"} ({productoDia?.cantidad || 0})</p>
            <p><strong>Producto del mes:</strong> {productoMes?.nombre || "Sin datos"} ({productoMes?.cantidad || 0})</p>
            <p><strong>Reservas pendientes:</strong> {metricas?.reservas?.reservas_pendientes || 0}</p>
            <button className="metricas-report-btn" type="button" onClick={onOpenReporte}>
              <i className="bi bi-bar-chart"></i>
              Ver reporte mensual
            </button>
          </div>
        </section>
      </section>
    </>
  );
}

function MetricasFullPro({ metricas, productos, onOpenReporte }) {
  const herramientasIa = [
    "IA para promociones",
    "IA para mejorar fotografías",
    "IA para descripciones de productos",
    "IA para publicaciones en redes sociales",
    "Recomendaciones para aumentar ventas",
  ];

  return (
    <>
      <MetricasPro metricas={metricas} productos={productos} onOpenReporte={onOpenReporte} />
      <section className="metricas-panel">
        <div className="metricas-panel-header">
          <div>
            <span>Full Pro</span>
            <h2>Herramientas IA</h2>
          </div>
        </div>
        <div className="metricas-ia-grid">
          {herramientasIa.map((herramienta) => (
            <article key={herramienta}>
              <i className="bi bi-stars"></i>
              <strong>{herramienta}</strong>
              <span>Próximamente</span>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

export default function MetricasDashboard() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [restaurante, setRestaurante] = useState(null);
  const [metricas, setMetricas] = useState(null);
  const [productos, setProductos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reporteAbierto, setReporteAbierto] = useState(false);
  const [reporteMensual, setReporteMensual] = useState(null);
  const [reporteLoading, setReporteLoading] = useState(false);
  const [reporteError, setReporteError] = useState("");

  const cargarDatos = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [restauranteResponse, metricasResponse, productosResponse] = await Promise.all([
        authFetch("/mi-restaurante/", { cache: "no-store" }),
        authFetch("/mi-restaurante/pedidos/metricas/", { cache: "no-store" }),
        authFetch("/mi-restaurante/productos-mas-clickeados/", { cache: "no-store" }),
      ]);

      const restauranteData = await restauranteResponse.json();
      if (!restauranteResponse.ok) throw new Error(restauranteData?.error || "No se pudo cargar el restaurante.");

      if (slug && slug !== restauranteData.restaurante.slug) {
        navigate(`/dashboard/${restauranteData.restaurante.slug}/metricas`, { replace: true });
        return;
      }

      const metricasData = await metricasResponse.json();
      if (!metricasResponse.ok) throw new Error(metricasData?.error || "No se pudieron cargar las metricas.");

      const productosData = await productosResponse.json();
      setRestaurante(restauranteData.restaurante);
      setMetricas(metricasData);
      setProductos(productosResponse.ok ? productosData || [] : []);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron cargar las metricas.");
    } finally {
      setLoading(false);
    }
  }, [navigate, slug]);

  useEffect(() => {
    cargarDatos();
  }, [cargarDatos]);

  const abrirReporteMensual = async () => {
    setReporteAbierto(true);
    setReporteLoading(true);
    setReporteError("");

    try {
      const response = await authFetch("/metricas/reporte-mensual/", { cache: "no-store" });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.error || "No se pudo cargar el reporte mensual.");
      }

      setReporteMensual(data);
    } catch (requestError) {
      setReporteMensual(null);
      setReporteError(requestError.message || "No se pudo cargar el reporte mensual.");
    } finally {
      setReporteLoading(false);
    }
  };

  const cerrarReporteMensual = () => {
    setReporteAbierto(false);
    setReporteError("");
  };

  const plan = restaurante?.plan || planFallback;
  const vista = useMemo(() => {
    if (plan.slug === "full_pro") {
      return <MetricasFullPro metricas={metricas || {}} productos={productos} onOpenReporte={abrirReporteMensual} />;
    }
    if (plan.slug === "pro") {
      return <MetricasPro metricas={metricas || {}} productos={productos} onOpenReporte={abrirReporteMensual} />;
    }
    return <MetricasBasicas metricas={metricas || {}} />;
  }, [metricas, plan.slug, productos]);

  if (loading) return <p className="reservas-loading">Cargando metricas...</p>;

  return (
    <div className="body">
      <main className="container-fluid" id="main">
        <MainMenu />
        <section className="metricas-page">
          <header className="metricas-header">
            <div>
              <h1>Métricas</h1>
              <p>Plan actual: <strong>{plan.nombre || "Básico"}</strong></p>
            </div>
          </header>
          {error ? <p className="reservas-error">{error}</p> : vista}
        </section>
        {reporteAbierto && (
          <ReporteMensualModal
            reporte={reporteMensual}
            loading={reporteLoading}
            error={reporteError}
            onClose={cerrarReporteMensual}
          />
        )}
      </main>
    </div>
  );
}
