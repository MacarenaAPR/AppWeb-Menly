import "../styles/style-componentes.css";
import { useNavigate } from "react-router-dom";

export default function Card({ titulo, icons, metrica, btnto }) {
  const navigate = useNavigate();
  return (
    <div className="card-metrics">
        <div className="cards-icon-text">
          <div className="icon-circle">
            <svg xmlns="http://www.w3.org/2000/svg" width="65" height="65" viewBox="0 0 65 65" fill="none">
              <circle cx="32.2581" cy="32.2581" r="32.2581" fill="url(#paint0_linear_83_37)"/>
              <defs>
                <linearGradient id="paint0_linear_83_37" x1="31.828" y1="-5.16129" x2="32.2581" y2="64.5161" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#F8761D"/>
                  <stop offset="0.9999" stopColor="#D44D29"/>
                </linearGradient>
              </defs>
            </svg>
            <i className={`bi ${icons}`}></i>
          </div>
          <div className="div-text-metric">
            <h1>{metrica}</h1>
            <p>{titulo}</p>

          </div>
        </div>
        
        <button 
          className="Button-detalles"
          onClick={() => navigate(btnto)}
        >
          <p>Ver detalles</p>
        </button>
        
      

    </div>
  );
}
