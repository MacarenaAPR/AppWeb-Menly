const formatCountdown = (totalSeconds = 0) => {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
};

export default function SessionExpiryModal({ warning, onKeepSession, onLogout }) {
  if (!warning) return null;

  return (
    <div className="session-expiry-backdrop" role="presentation">
      <section
        className="session-expiry-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-expiry-title"
        aria-describedby="session-expiry-description"
      >
        <span className="session-expiry-icon" aria-hidden="true">
          <i className="bi bi-clock-history"></i>
        </span>
        <h2 id="session-expiry-title">Tu sesión está por finalizar</h2>
        <p id="session-expiry-description">
          La sesión se cerrará por inactividad si no realizas ninguna acción.
        </p>
        <strong className="session-expiry-countdown" aria-live="polite">
          {formatCountdown(warning.remainingSeconds)}
        </strong>
        <div className="session-expiry-actions">
          <button type="button" className="session-expiry-logout" onClick={onLogout}>
            Cerrar sesión
          </button>
          <button type="button" className="session-expiry-keep" onClick={onKeepSession} autoFocus>
            Mantener sesión
          </button>
        </div>
      </section>
    </div>
  );
}
