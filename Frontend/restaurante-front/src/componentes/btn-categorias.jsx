import "../styles/style-componentes.css";

export default function ButtonCategoria({ name, active, onClick, icon }) {
  return (
    <button
      className={`btn-categoria ${active ? "active" : ""}`}
      onClick={onClick}
    >
      {icon && <i className={`bi ${icon}`}></i>}
      <p>{name}</p>
    </button>
  );
}