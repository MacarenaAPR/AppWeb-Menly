import "../styles/RestaurantPageLoader.css";
import logoMenly from "../assets/logoMenly.png";

export default function RestaurantPageLoader({ logoUrl }) {
  return (
    <div className="restaurant-loader">
      <div className="restaurant-loader__box">
        <img
          src={logoUrl || logoMenly}
          alt="Cargando restaurante"
          className="restaurant-loader__logo"
        />
        <p>Cargando experiencia...</p>
        <div className="restaurant-loader__spinner" />
      </div>
    </div>
  );
}