import { useCallback, useEffect, useMemo, useState } from "react";
import QRCode from "qrcode";
import { buildMenuUrl } from "../../api";

export default function Impresion() {
  const [error, setError] = useState("");
  const [urlMenu] = useState(() => {
    const restaurante = JSON.parse(localStorage.getItem("restaurante"));

    if (!restaurante) return "";

    return buildMenuUrl(restaurante.slug);
  });
  const qrKey = useMemo(() => {
    const restaurante = JSON.parse(localStorage.getItem("restaurante") || "null");
    return urlMenu ? `menuo_qr_${restaurante?.slug || urlMenu}` : "";
  }, [urlMenu]);
  const [qr, setQr] = useState(() => {
    const restaurante = JSON.parse(localStorage.getItem("restaurante") || "null");
    const menuUrl = restaurante ? buildMenuUrl(restaurante.slug) : "";
    const storageKey = menuUrl ? `menuo_qr_${restaurante?.slug || menuUrl}` : "";

    return storageKey ? localStorage.getItem(storageKey) || "" : "";
  });

  const generarQR = useCallback(async (url, key) => {
    try {
      const qrData = await QRCode.toDataURL(url);
      localStorage.setItem(key, qrData);
      setQr(qrData);
    } catch {
      setError("No se pudo generar el código QR");
    }
  }, []);

  useEffect(() => {
    if (!urlMenu) return;
    if (qr) return;

    const timeoutId = window.setTimeout(() => {
      generarQR(urlMenu, qrKey);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [generarQR, qr, qrKey, urlMenu]);

  const descargarQR = () => {
    const link = document.createElement("a");
    link.href = qr;
    link.download = "menu-qr.png";
    link.click();
  };

  return (
    <div className="impresion-panel">
      <div className="usuarios-title">
        <i className="bi bi-qr-code"></i>
        <div>
          <h2>Impresión</h2>
          <p>Genera un código QR para que tus clientes accedan al menú.</p>
        </div>
      </div>

      <section className="usuarios-card impresion-card">
        <h3>Código QR del menú</h3>
        {error && <p className="empty-text">{error}</p>}

        <div className="qr-box">
          {qr ? (
            <img src={qr} alt="QR Menu" />
          ) : (
            <p>Generando QR...</p>
          )}
        </div>

        <div className="qr-actions">
          <button className="usuarios-save-btn" onClick={descargarQR}>
            Descargar QR
          </button>
        </div>

        <div className="qr-url">
          <p>Link del menú:</p>
          <div className="url-box">
            <input value={urlMenu} readOnly />
            <button
              onClick={() => navigator.clipboard.writeText(urlMenu)}
            >
              Copiar
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
