export default function FeatureFlipCard({
  icon,
  title,
  description,
  isActive,
  onToggle,
  accordionId,
}) {
  return (
    <button
      type="button"
      className={`feature-flip-card ${isActive ? "is-flipped" : ""}`}
      aria-pressed={isActive}
      aria-expanded={isActive}
      aria-controls={accordionId}
      onClick={onToggle}
    >
      <span className="feature-flip-card__inner">
        <span className="feature-flip-card__face feature-flip-card__front">
          <span className="feature-flip-card__icon feature-flip-card__icon--front">
            <i className={`bi ${icon}`} aria-hidden="true"></i>
          </span>
          <span className="feature-flip-card__title">{title}</span>
          <span className="feature-flip-card__accordion-arrow" aria-hidden="true">
            <i className="bi bi-chevron-down"></i>
          </span>
        </span>

        <span className="feature-flip-card__face feature-flip-card__back" id={accordionId}>
          <span className="feature-flip-card__back-title">{title}</span>
          <span className="feature-flip-card__description">{description}</span>
        </span>
      </span>
    </button>
  );
}
