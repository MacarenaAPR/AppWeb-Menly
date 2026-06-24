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

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

const productoTexto = (producto) =>
  producto ? `${producto.nombre} (${producto.cantidad})` : "Sin datos";

const descargarPdfAnual = (reporte) => {
  if (!reporte) return;

  const pdf = new jsPDF("p", "mm", "a4");
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 16;
  const contentWidth = pageWidth - margin * 2;
  const footerY = pageHeight - 12;
  let y = 18;
  const fechaDescarga = new Date().toLocaleDateString("es-CL", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

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
  const addTitle = (title) => {
    ensureSpace(12);
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(14);
    pdf.setTextColor(20, 28, 38);
    pdf.text(title, margin, y);
    y += 8;
  };
  const addText = (label, value) => {
    ensureSpace(8);
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(10);
    pdf.setTextColor(20, 28, 38);
    pdf.text(`${label}:`, margin, y);
    pdf.setFont("helvetica", "normal");
    pdf.text(String(value ?? "Sin datos"), margin + 48, y);
    y += 7;
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
      pdf.setFillColor(rowIndex % 2 === 0 ? 248 : 251, rowIndex % 2 === 0 ? 250 : 252, rowIndex % 2 === 0 ? 252 : 253);
      pdf.rect(margin, y, contentWidth, rowHeight, "F");
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9);
      pdf.setTextColor(32, 40, 52);
      let x = margin + 3;
      row.forEach((cell, index) => {
        pdf.text(pdf.splitTextToSize(String(cell ?? "-"), widths[index] - 6).slice(0, 1), x, y + 5.5);
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
  pdf.text("Reporte anual Menly", margin, y);
  y += 9;
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(11);
  pdf.setTextColor(90, 100, 115);
  pdf.text(`Año: ${reporte.anio || "Año actual"}`, margin, y);
  y += 12;

  addTitle("Resumen anual");
  addText("Venta total", formatearMoneda(reporte.venta_total_anual));
  addText("Pedidos totales", reporte.pedidos_total_anual ?? 0);
  addText("Pedidos cancelados", reporte.pedidos_cancelados_anual ?? 0);
  addText("Mes mayor venta", `${reporte.mes_mayor_venta?.nombre_mes || "-"} · ${formatearMoneda(reporte.mes_mayor_venta?.total)}`);
  addText("Mes menor venta", `${reporte.mes_menor_venta?.nombre_mes || "-"} · ${formatearMoneda(reporte.mes_menor_venta?.total)}`);
  addText("Producto más vendido", productoTexto(reporte.producto_mas_vendido_anual));
  addText("Producto menos vendido", productoTexto(reporte.producto_menos_vendido_anual));
  y += 4;

  addTitle("Ventas por mes");
  addTable(
    ["Mes", "Total", "Pedidos", "Cancelados"],
    (reporte.ventas_por_mes || []).map((item) => [
      item.nombre_mes || MESES[(item.mes || 1) - 1],
      formatearMoneda(item.total),
      item.pedidos ?? 0,
      item.cancelados ?? 0,
    ]),
    [56, 48, 36, contentWidth - 140],
  );

  addTitle("Resumen de productos");
  addTable(
    ["Producto", "Cantidad", "Total vendido"],
    (reporte.productos_vendidos || []).length
      ? reporte.productos_vendidos.map((producto) => [
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
  pdf.save(`reporte-anual-menly-${reporte.anio}.pdf`);
};

const descargarPdfMensualGuardado = (reporte) => {
  if (!reporte) return;

  const pdf = new jsPDF("p", "mm", "a4");
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 16;
  const footerY = pageHeight - 12;
  let y = 18;
  const addFooter = () => {
    pdf.setFontSize(9);
    pdf.setTextColor(110, 120, 135);
    pdf.text("Generado por Menly", margin, footerY);
    pdf.text(`Fecha de descarga: ${new Date().toLocaleString("es-CL")}`, pageWidth - margin, footerY, { align: "right" });
  };
  const ensureSpace = () => {
    if (y <= footerY - 12) return;
    addFooter();
    pdf.addPage();
    y = 18;
  };
  const line = (label, value) => {
    ensureSpace();
    pdf.setFont("helvetica", "bold");
    pdf.setTextColor(20, 28, 38);
    pdf.text(`${label}:`, margin, y);
    pdf.setFont("helvetica", "normal");
    pdf.text(String(value ?? "Sin datos"), margin + 52, y);
    y += 8;
  };

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(22);
  pdf.text("Reporte mensual Menly", margin, y);
  y += 12;
  pdf.setFontSize(10);
  line("Mes", reporte.mes || "Mes actual");
  line("Venta total", formatearMoneda(reporte.venta_total));
  line("Pedidos totales", reporte.pedidos_total ?? 0);
  line("Pedidos cancelados", reporte.pedidos_cancelados ?? 0);
  line("Día mayor venta", `Día ${reporte.dia_mayor_venta?.dia || "-"} · ${formatearMoneda(reporte.dia_mayor_venta?.total)}`);
  line("Día menor venta", `Día ${reporte.dia_menor_venta?.dia || "-"} · ${formatearMoneda(reporte.dia_menor_venta?.total)}`);
  line("Producto más vendido", productoTexto(reporte.producto_mas_vendido));
  line("Producto menos vendido", productoTexto(reporte.producto_menos_vendido));
  y += 6;

  pdf.setFont("helvetica", "bold");
  pdf.text("Ventas diarias", margin, y);
  y += 8;
  (reporte.venta_diaria || []).forEach((item) => {
    ensureSpace();
    pdf.setFont("helvetica", "normal");
    pdf.text(`Día ${item.dia}`, margin, y);
    pdf.text(formatearMoneda(item.total), pageWidth - margin, y, { align: "right" });
    y += 7;
  });

  y += 6;
  pdf.setFont("helvetica", "bold");
  pdf.text("Resumen de productos", margin, y);
  y += 8;
  const productos = reporte.productos_vendidos?.length
    ? reporte.productos_vendidos
    : [reporte.producto_mas_vendido, reporte.producto_menos_vendido].filter(Boolean);
  if (productos.length === 0) {
    ensureSpace();
    pdf.setFont("helvetica", "normal");
    pdf.text("Sin datos", margin, y);
    y += 7;
  } else {
    productos.forEach((producto) => {
      ensureSpace();
      pdf.setFont("helvetica", "normal");
      pdf.text(producto.nombre || "Sin datos", margin, y);
      pdf.text(`${producto.cantidad ?? 0} unidades`, pageWidth - margin, y, { align: "right" });
      y += 7;
    });
  }

  addFooter();
  pdf.save(`reporte-mensual-menly-${reporte.mes}.pdf`);
};

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
  const ventaMensual = metricas?.ventas?.venta_real_mes || 0;
  const pedidosMes = metricas?.pedidos?.pedidos_creados_mes || 0;
  const pedidosEspecialesMes = metricas?.canales?.especiales?.pedidos_creados_mes || 0;

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
              <small>{producto.cantidad ?? producto.clicks ?? 0} vendidos</small>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function ReporteMensualModal({ reporte, loading, error, onClose, onGuardar, guardando }) {
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
            <div className="metricas-modal-actions">
              <button className="metricas-report-btn" type="button" onClick={onGuardar} disabled={guardando}>
                <i className="bi bi-save"></i>
                {guardando ? "Guardando..." : "Guardar reporte"}
              </button>
              <button className="metricas-report-btn" type="button" onClick={descargarPdf}>
                <i className="bi bi-download"></i>
                Descargar PDF
              </button>
            </div>
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

function ReporteAnualModal({ reporte, loading, error, onClose, onGuardar, guardando }) {
  const ventasPorMes = reporte?.ventas_por_mes || [];
  const chartOptions = useMemo(() => ({
    chart: {
      type: "bar",
      background: "transparent",
      toolbar: { show: false },
      animations: { enabled: true, easing: "easeinout", speed: 650 },
      foreColor: "#94a3b8",
    },
    theme: { mode: "dark" },
    colors: ["#f8761d"],
    plotOptions: { bar: { borderRadius: 6, columnWidth: "58%" } },
    dataLabels: { enabled: false },
    grid: { borderColor: "#172535", strokeDashArray: 4 },
    xaxis: {
      categories: ventasPorMes.map((item) => item.nombre_mes || MESES[(item.mes || 1) - 1]),
      labels: { style: { colors: "#94a3b8" } },
      axisBorder: { color: "#1e2d3d" },
      axisTicks: { color: "#1e2d3d" },
    },
    yaxis: {
      labels: {
        formatter: (value) => `$${Number(value).toLocaleString("es-CL")}`,
        style: { colors: "#94a3b8" },
      },
    },
    tooltip: {
      theme: "dark",
      y: {
        formatter: (value) => formatearMoneda(value),
        title: { formatter: () => "Venta" },
      },
    },
    responsive: [{ breakpoint: 768, options: { plotOptions: { bar: { columnWidth: "74%" } } } }],
  }), [ventasPorMes]);

  const chartSeries = useMemo(() => ([
    {
      name: "Venta",
      data: ventasPorMes.map((item) => Number(item.total || 0)),
    },
  ]), [ventasPorMes]);

  return (
    <div className="metricas-modal-backdrop" role="dialog" aria-modal="true">
      <section className="metricas-modal">
        <button className="metricas-modal-close" type="button" onClick={onClose} aria-label="Cerrar">
          <i className="bi bi-x-lg"></i>
        </button>

        <header className="metricas-modal-header">
          <div>
            <span>Reporte anual</span>
            <h2>{reporte?.anio || "Año actual"}</h2>
          </div>
          {reporte && (
            <div className="metricas-modal-actions">
              <button className="metricas-report-btn" type="button" onClick={onGuardar} disabled={guardando}>
                <i className="bi bi-save"></i>
                {guardando ? "Guardando..." : "Guardar reporte"}
              </button>
              <button className="metricas-report-btn" type="button" onClick={() => descargarPdfAnual(reporte)}>
                <i className="bi bi-download"></i>
                Descargar PDF
              </button>
            </div>
          )}
        </header>

        {loading ? (
          <p className="metricas-empty">Cargando reporte anual...</p>
        ) : error ? (
          <p className="metricas-error">{error}</p>
        ) : reporte ? (
          <>
            <section className="metricas-reporte-grid">
              <MetricCard icon="bi bi-currency-dollar" label="Venta anual" value={formatearMoneda(reporte.venta_total_anual)} />
              <MetricCard icon="bi bi-bag-check" label="Pedidos totales" value={reporte.pedidos_total_anual} />
              <MetricCard icon="bi bi-x-circle" label="Cancelados" value={reporte.pedidos_cancelados_anual} />
              <MetricCard icon="bi bi-graph-up-arrow" label="Mes mayor venta" value={reporte.mes_mayor_venta?.nombre_mes || "-"} hint={formatearMoneda(reporte.mes_mayor_venta?.total)} />
              <MetricCard icon="bi bi-graph-down-arrow" label="Mes menor venta" value={reporte.mes_menor_venta?.nombre_mes || "-"} hint={formatearMoneda(reporte.mes_menor_venta?.total)} />
              <MetricCard icon="bi bi-trophy" label="Más vendido" value={productoTexto(reporte.producto_mas_vendido_anual)} />
              <MetricCard icon="bi bi-box" label="Menos vendido" value={productoTexto(reporte.producto_menos_vendido_anual)} />
            </section>

            <section className="metricas-panel metricas-chart-panel">
              <div className="metricas-panel-header">
                <div>
                  <span>Ventas por mes</span>
                  <h2>Enero a diciembre</h2>
                </div>
              </div>
              <div className="metricas-chart-wrap">
                <Chart options={chartOptions} series={chartSeries} type="bar" height={320} />
              </div>
            </section>

            <section className="metricas-panel">
              <div className="metricas-panel-header">
                <div>
                  <span>Tabla anual</span>
                  <h2>Ventas por mes</h2>
                </div>
              </div>
              <div className="metricas-report-table">
                {ventasPorMes.map((item) => (
                  <div key={item.mes}>
                    <strong>{item.nombre_mes || MESES[item.mes - 1]}</strong>
                    <span>{formatearMoneda(item.total)}</span>
                    <small>{item.pedidos} pedidos · {item.cancelados} cancelados</small>
                  </div>
                ))}
              </div>
            </section>
          </>
        ) : null}
      </section>
    </div>
  );
}

function MetricasPro({ metricas, productos, onOpenReporteMensual, onOpenReporteAnual }) {
  const productoDia = metricas?.productos?.mas_vendido_hoy;
  const productoMes = metricas?.productos?.mas_vendido_mes;

  return (
    <>
      <section className="metricas-grid">
        <MetricCard icon="bi bi-eye" label="Visitas" value={metricas?.productos?.clicks_total || 0} hint="Clicks en productos" />
        <MetricCard icon="bi bi-bag-check" label="Pedidos creados mes" value={metricas?.pedidos?.pedidos_creados_mes || 0} />
        <MetricCard icon="bi bi-calendar2-check" label="Reservas programadas mes" value={metricas?.reservas?.reservas_programadas_mes || 0} />
        <MetricCard icon="bi bi-x-circle" label="Pedidos cancelados" value={metricas?.pedidos?.pedidos_cancelados_mes || 0} />
      </section>
      <section className="metricas-grid">
        <MetricCard icon="bi bi-cash-stack" label="Venta diaria" value={formatearMoneda(metricas?.ventas?.venta_real_hoy || 0)} />
        <MetricCard icon="bi bi-graph-up-arrow" label="Venta semanal" value={formatearMoneda(metricas?.ventas?.venta_real_semana || 0)} />
        <MetricCard icon="bi bi-calendar3" label="Venta mensual" value={formatearMoneda(metricas?.ventas?.venta_real_mes || 0)} />
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
            <p><strong>Reservas pendientes futuras:</strong> {metricas?.reservas?.reservas_pendientes_futuras || 0}</p>
            <button className="metricas-report-btn" type="button" onClick={onOpenReporteMensual}>
              <i className="bi bi-bar-chart"></i>
              Ver reporte mensual
            </button>
            <button className="metricas-report-btn" type="button" onClick={onOpenReporteAnual}>
              <i className="bi bi-calendar3"></i>
              Ver reporte anual
            </button>
          </div>
        </section>
      </section>
    </>
  );
}

function MetricasFullPro({ metricas, productos, onOpenReporteMensual, onOpenReporteAnual }) {
  const herramientasIa = [
    "IA para promociones",
    "IA para mejorar fotografías",
    "IA para descripciones de productos",
    "IA para publicaciones en redes sociales",
    "Recomendaciones para aumentar ventas",
  ];

  return (
    <>
      <MetricasPro
        metricas={metricas}
        productos={productos}
        onOpenReporteMensual={onOpenReporteMensual}
        onOpenReporteAnual={onOpenReporteAnual}
      />
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

function ReportesGuardados({ refreshKey }) {
  const [reportes, setReportes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filtros, setFiltros] = useState({ tipo: "", anio: "", mes: "" });
  const [detalle, setDetalle] = useState(null);
  const [detalleLoading, setDetalleLoading] = useState(false);

  const cargarReportes = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (filtros.tipo) params.set("tipo", filtros.tipo);
    if (filtros.anio) params.set("anio", filtros.anio);
    if (filtros.mes) params.set("mes", filtros.mes);

    try {
      const response = await authFetch(`/metricas/reportes/${params.toString() ? `?${params}` : ""}`, {
        cache: "no-store",
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.error || "No se pudieron cargar los reportes.");
      setReportes(data || []);
    } catch (requestError) {
      setReportes([]);
      setError(requestError.message || "No se pudieron cargar los reportes.");
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => {
    cargarReportes();
  }, [cargarReportes, refreshKey]);

  const verDetalle = async (id) => {
    setDetalleLoading(true);
    setError("");
    try {
      const response = await authFetch(`/metricas/reportes/${id}/`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.error || "No se pudo cargar el detalle.");
      setDetalle(data);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el detalle.");
    } finally {
      setDetalleLoading(false);
    }
  };

  const descargarReporte = (reporte) => {
    if (reporte.tipo === "anual") {
      descargarPdfAnual(reporte.datos);
      return;
    }
    descargarPdfMensualGuardado(reporte.datos);
  };

  const periodoReporte = (reporte) => reporte.tipo === "anual" ? reporte.periodo_anio : reporte.periodo_mes;

  return (
    <section className="metricas-panel metricas-guardados">
      <div className="metricas-panel-header">
        <div>
          <span>Historial</span>
          <h2>Reportes guardados</h2>
        </div>
      </div>

      <div className="metricas-filtros-reportes">
        <select value={filtros.tipo} onChange={(event) => setFiltros((prev) => ({ ...prev, tipo: event.target.value }))}>
          <option value="">Todos</option>
          <option value="mensual">Mensual</option>
          <option value="anual">Anual</option>
        </select>
        <input value={filtros.anio} onChange={(event) => setFiltros((prev) => ({ ...prev, anio: event.target.value }))} placeholder="Año" />
        <input value={filtros.mes} onChange={(event) => setFiltros((prev) => ({ ...prev, mes: event.target.value }))} placeholder="Mes YYYY-MM" />
      </div>

      {loading ? (
        <p className="metricas-empty">Cargando reportes...</p>
      ) : error ? (
        <p className="metricas-error">{error}</p>
      ) : reportes.length === 0 ? (
        <p className="metricas-empty">Aún no hay reportes guardados.</p>
      ) : (
        <div className="metricas-reportes-list">
          {reportes.map((reporte) => (
            <article key={reporte.id}>
              <div>
                <span>{reporte.tipo_display}</span>
                <strong>{reporte.titulo}</strong>
                <small>{periodoReporte(reporte)} · {new Date(reporte.fecha_generacion).toLocaleString("es-CL")}</small>
              </div>
              <div className="metricas-reportes-actions">
                <button type="button" onClick={() => verDetalle(reporte.id)} disabled={detalleLoading}>Ver detalle</button>
                <button type="button" onClick={() => descargarReporte(reporte)}>Descargar PDF</button>
              </div>
            </article>
          ))}
        </div>
      )}

      {detalle && (
        <div className="metricas-modal-backdrop" role="dialog" aria-modal="true">
          <section className="metricas-modal metricas-modal-compact">
            <button className="metricas-modal-close" type="button" onClick={() => setDetalle(null)} aria-label="Cerrar">
              <i className="bi bi-x-lg"></i>
            </button>
            <header className="metricas-modal-header">
              <div>
                <span>{detalle.tipo_display}</span>
                <h2>{detalle.titulo}</h2>
                <p>{periodoReporte(detalle)}</p>
              </div>
              <button className="metricas-report-btn" type="button" onClick={() => descargarReporte(detalle)}>
                <i className="bi bi-download"></i>
                Descargar PDF
              </button>
            </header>
            <pre className="metricas-json-preview">{JSON.stringify(detalle.resumen || detalle.datos, null, 2)}</pre>
          </section>
        </div>
      )}
    </section>
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
  const [reporteAnualAbierto, setReporteAnualAbierto] = useState(false);
  const [reporteAnual, setReporteAnual] = useState(null);
  const [reporteAnualLoading, setReporteAnualLoading] = useState(false);
  const [reporteAnualError, setReporteAnualError] = useState("");
  const [guardandoReporte, setGuardandoReporte] = useState(false);
  const [reportesRefreshKey, setReportesRefreshKey] = useState(0);

  const cargarDatos = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [restauranteResponse, metricasResponse, productosResponse] = await Promise.all([
        authFetch("/mi-restaurante/", { cache: "no-store" }),
        authFetch("/mi-restaurante/metricas/resumen/", { cache: "no-store" }),
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
      setProductos(metricasData?.productos?.top_por_cantidad || (productosResponse.ok ? productosData || [] : []));
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

  const abrirReporteAnual = async () => {
    setReporteAnualAbierto(true);
    setReporteAnualLoading(true);
    setReporteAnualError("");

    try {
      const response = await authFetch("/metricas/reporte-anual/", { cache: "no-store" });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.error || "No se pudo cargar el reporte anual.");
      }

      setReporteAnual(data);
    } catch (requestError) {
      setReporteAnual(null);
      setReporteAnualError(requestError.message || "No se pudo cargar el reporte anual.");
    } finally {
      setReporteAnualLoading(false);
    }
  };

  const cerrarReporteAnual = () => {
    setReporteAnualAbierto(false);
    setReporteAnualError("");
  };

  const guardarReporte = async (tipo, reporte) => {
    if (!reporte) return;
    setGuardandoReporte(true);

    const esMensual = tipo === "mensual";
    const payload = {
      tipo,
      periodo_mes: esMensual ? reporte.mes : null,
      periodo_anio: esMensual ? reporte.mes?.split("-")[0] : reporte.anio,
      titulo: esMensual ? `Reporte mensual Menly ${reporte.mes}` : `Reporte anual Menly ${reporte.anio}`,
      resumen: esMensual
        ? {
            venta_total: reporte.venta_total,
            pedidos_total: reporte.pedidos_total,
            pedidos_cancelados: reporte.pedidos_cancelados,
            dia_mayor_venta: reporte.dia_mayor_venta,
            dia_menor_venta: reporte.dia_menor_venta,
            producto_mas_vendido: reporte.producto_mas_vendido,
            producto_menos_vendido: reporte.producto_menos_vendido,
          }
        : {
            venta_total_anual: reporte.venta_total_anual,
            pedidos_total_anual: reporte.pedidos_total_anual,
            pedidos_cancelados_anual: reporte.pedidos_cancelados_anual,
            mes_mayor_venta: reporte.mes_mayor_venta,
            mes_menor_venta: reporte.mes_menor_venta,
            producto_mas_vendido_anual: reporte.producto_mas_vendido_anual,
            producto_menos_vendido_anual: reporte.producto_menos_vendido_anual,
          },
      datos: reporte,
    };

    try {
      const response = await authFetch("/metricas/reportes/guardar/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.error || "No se pudo guardar el reporte.");
      setReportesRefreshKey((prev) => prev + 1);
    } catch (requestError) {
      const mensaje = requestError.message || "No se pudo guardar el reporte.";
      if (esMensual) setReporteError(mensaje);
      else setReporteAnualError(mensaje);
    } finally {
      setGuardandoReporte(false);
    }
  };

  const plan = restaurante?.plan || planFallback;
  const vista = useMemo(() => {
    if (plan.slug === "full_pro") {
      return (
        <MetricasFullPro
          metricas={metricas || {}}
          productos={productos}
          onOpenReporteMensual={abrirReporteMensual}
          onOpenReporteAnual={abrirReporteAnual}
        />
      );
    }
    if (plan.slug === "pro") {
      return (
        <MetricasPro
          metricas={metricas || {}}
          productos={productos}
          onOpenReporteMensual={abrirReporteMensual}
          onOpenReporteAnual={abrirReporteAnual}
        />
      );
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
          {error ? <p className="reservas-error">{error}</p> : (
            <>
              {vista}
              {["pro", "full_pro"].includes(plan.slug) && (
                <ReportesGuardados refreshKey={reportesRefreshKey} />
              )}
            </>
          )}
        </section>
        {reporteAbierto && (
          <ReporteMensualModal
            reporte={reporteMensual}
            loading={reporteLoading}
            error={reporteError}
            onClose={cerrarReporteMensual}
            onGuardar={() => guardarReporte("mensual", reporteMensual)}
            guardando={guardandoReporte}
          />
        )}
        {reporteAnualAbierto && (
          <ReporteAnualModal
            reporte={reporteAnual}
            loading={reporteAnualLoading}
            error={reporteAnualError}
            onClose={cerrarReporteAnual}
            onGuardar={() => guardarReporte("anual", reporteAnual)}
            guardando={guardandoReporte}
          />
        )}
      </main>
    </div>
  );
}
