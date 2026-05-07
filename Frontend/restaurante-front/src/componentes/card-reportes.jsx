import "../styles/style-componentes.css";
export default function CardReports({ fecha_cambio, Estado, Producto, descripcion, usuario }) {
  return (
    <div className="cardreports">
      <div className="cardreports2">
        <div className="icon-circle-green">
          <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40" fill="none">
            <circle cx="19.5842" cy="19.5843" r="19.5843" fill="#074624"/>
          </svg>
          <i className="bi bi-pencil-fill"></i>
        </div> 
        
        <div className="div-txt-cards-reports">
          <p className="p-txt">Accion: {Estado}</p>
          <p>Producto: {Producto}</p>
          <p>{descripcion}</p>
          <p>{usuario}</p>
        </div>
      </div>
      
      <p> fecha :{fecha_cambio}</p>  
    </div>
  );
}
