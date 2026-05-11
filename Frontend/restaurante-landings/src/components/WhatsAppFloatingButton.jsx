const WHATSAPP_MESSAGE = "Hola, quisiera hacer una consulta.";

const limpiarTelefonoWhatsApp = (telefono = "") =>
  String(telefono).replace(/[\s+\-()]/g, "");

export default function WhatsAppFloatingButton({ telefono }) {
  const numero = limpiarTelefonoWhatsApp(telefono);

  if (!numero) return null;

  const url = `https://wa.me/${numero}?text=${encodeURIComponent(WHATSAPP_MESSAGE)}`;

  return (
    <a
      className="whatsapp-floating-btn"
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Contactar por WhatsApp"
    >
      <i className="bi bi-whatsapp" aria-hidden="true"></i>
      <span>WhatsApp</span>
    </a>
  );
}
