import "../styles/style-componentes.css";

export default function ButtonMain({icon, name, onClick }) {
  return (
    <button className="btn-main-componente" onClick={onClick}>
        <i>{icon}</i>
        <p>{name}</p>
    </button>
  );
}
