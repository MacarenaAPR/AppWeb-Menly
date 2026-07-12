import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { cocinaFetch, readJsonResponse } from "../api";
import "../styles/Cocina.css";

export default function CocinaActivar() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState("");

  const activacionIniciadaRef = useRef(false);

  useEffect(() => {
    if (!token || activacionIniciadaRef.current) {
      return;
    }

    activacionIniciadaRef.current = true;

    const activar = async () => {
      try {
        const response = await cocinaFetch(
          `/cocina/activar/${encodeURIComponent(token)}/`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
          }
        );

        await readJsonResponse(
          response,
          "/cocina/activar/",
          "Este enlace de activación ya no es válido."
        );

        navigate("/pedidos-cocina", {
          replace: true,
        });
      } catch (error) {
        console.error("Error al activar cocina:", error);

        setError(
          error?.message ||
            "Este enlace de activación ya no es válido. Solicita uno nuevo desde el panel de Menly."
        );
      }
    };

    activar();
  }, [navigate, token]);

  return (
    <main className="cocina-auth-page">
      <section className="cocina-auth-card">
        <span>Menly Cocina</span>

        <h1>
          {error
            ? "No se pudo activar cocina"
            : "Activando cocina..."}
        </h1>

        <p>
          {error ||
            "Estamos creando una sesión exclusiva para esta pantalla."}
        </p>
      </section>
    </main>
  );
}