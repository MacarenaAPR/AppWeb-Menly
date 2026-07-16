import { useCallback, useEffect, useRef, useState } from "react";
import "../../styles/DemosCoverflow.css";

const DEMOS_AUTOPLAY_MS = 4000;

export default function DemosCoverflow({ demos }) {
  const [activeDemo, setActiveDemo] = useState(0);
  const [isInteracting, setIsInteracting] = useState(false);
  const dragStartX = useRef(null);

  const moveDemo = useCallback((direction) => {
    setActiveDemo((current) => {
      const total = demos.length;
      return (current + direction + total) % total;
    });
  }, [demos.length]);

  const getDemoPosition = (index) => {
    const total = demos.length;
    let offset = index - activeDemo;

    if (offset > total / 2) offset -= total;
    if (offset < -total / 2) offset += total;

    return offset;
  };

  const startDrag = (event) => {
    dragStartX.current = event.clientX;
    setIsInteracting(true);
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const endDrag = (event) => {
    if (dragStartX.current === null) {
      setIsInteracting(false);
      return;
    }

    const deltaX = event.clientX - dragStartX.current;

    if (Math.abs(deltaX) > 46) {
      moveDemo(deltaX < 0 ? 1 : -1);
    }

    dragStartX.current = null;
    setIsInteracting(false);
  };

  const cancelDrag = () => {
    dragStartX.current = null;
    setIsInteracting(false);
  };

  useEffect(() => {
    if (isInteracting || demos.length < 2) return undefined;

    const autoplay = window.setInterval(() => {
      moveDemo(1);
    }, DEMOS_AUTOPLAY_MS);

    return () => window.clearInterval(autoplay);
  }, [demos.length, isInteracting, moveDemo]);

  return (
    <div className="saber-web-demos" id="demos-web">
      <div className="saber-section__heading saber-section__heading--center">
        <span className="saber-kicker">DEMOSTRACIONES REALES</span>
        <h2>Conoce algunos dise&ntilde;os creados con Menly</h2>
        <p>
          Cada restaurante tiene una identidad diferente. Estas son algunas
          demostraciones.
        </p>
      </div>

      <div
        className="demos-coverflow"
        aria-label="Demostraciones reales de Menly"
        onPointerEnter={() => setIsInteracting(true)}
        onPointerLeave={() => {
          cancelDrag();
        }}
      >
        <div
          className="demos-coverflow__stage"
          onPointerDown={startDrag}
          onPointerUp={endDrag}
          onPointerCancel={cancelDrag}
        >
          {demos.map((demo, index) => {
            const position = getDemoPosition(index);

            return (
              <article
                className={`demos-coverflow__card ${position === 0 ? "is-active" : ""}`}
                data-coverflow-position={position}
                key={demo.nombre}
                aria-hidden={Math.abs(position) > 1}
              >
                <img
                  src={demo.img}
                  alt={`Captura de la landing ${demo.nombre}`}
                  loading="lazy"
                  draggable="false"
                />
                <div className="demos-coverflow__overlay">
                  <div>
                    <span>{demo.categoria}</span>
                    <h3>{demo.nombre}</h3>
                  </div>
                  <a
                    href={demo.url}
                  >
                    Ver pagina en vivo
                  </a>
                </div>
              </article>
            );
          })}
        </div>

        <button
          type="button"
          className="demos-coverflow__nav demos-coverflow__nav--prev"
          aria-label="Ver demo anterior"
          onClick={() => moveDemo(-1)}
        >
          <i className="bi bi-chevron-left" aria-hidden="true"></i>
        </button>
        <button
          type="button"
          className="demos-coverflow__nav demos-coverflow__nav--next"
          aria-label="Ver siguiente demo"
          onClick={() => moveDemo(1)}
        >
          <i className="bi bi-chevron-right" aria-hidden="true"></i>
        </button>

        <div className="demos-coverflow__dots" aria-label="Selector de demos">
          {demos.map((demo, index) => (
            <button
              type="button"
              className={index === activeDemo ? "is-active" : ""}
              key={demo.nombre}
              aria-label={`Ver ${demo.nombre}`}
              aria-current={index === activeDemo ? "true" : undefined}
              onClick={() => setActiveDemo(index)}
            ></button>
          ))}
        </div>
      </div>
    </div>
  );
}
