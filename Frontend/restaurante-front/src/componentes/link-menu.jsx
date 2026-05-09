import "../styles/style-componentes.css";

export default function ButtonMain({icon, name, onClick, className = "" }) {
  return (
    <button className={`btn-main-componente ${className}`.trim()} onClick={onClick} type="button">
        <i>{icon}</i>
        <p>{name}</p>
    </button>
  );
}
