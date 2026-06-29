import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import "bootstrap-icons/font/bootstrap-icons.css";
import PublicNavbar from "../componentes/public/PublicNavbar";
import FeatureFlipCard from "../componentes/public/FeatureFlipCard";
import "../styles/SaberMas.css";
import demosmash from "../assets/demo-smash-house.png";
import demobakry from "../assets/demo-bakry.png";
import demosmarea from "../assets/demo-marea-azul.png";
import previewPanel from "../assets/recursologin1.png";
import previewCarta from "../assets/recursologin3.png";
import previewWeb from "../assets/recursologin2.png";
import recursometrica from "../assets/recursometrica.png";
import recursodashboard from "../assets/recursodashboard.png";
import recursoproductos from "../assets/recursoproductos.png";
import fotoBowl from "../assets/Bowl_de_salteado_colorido_y_sabroso-removebg-preview.png";
import fotoVegetales from "../assets/Ilustración minimalista de vegetales.png";
import fotoPlato from "../assets/Plato rústico con carne desmenuzada.png";
import recursoWeb from "../assets/Recurso2.webp";
import logoMenly from "../assets/logoMenly2.png";
import recursopersona from "../assets/recursopersona.png";

const WHATSAPP_GENERAL =
  "https://wa.me/56988424939?text=Hola%2C%20quiero%20saber%20m%C3%A1s%20sobre%20Menly";

const problemasSoluciones = [
  {
    problema: "Recibes pedidos desordenados por WhatsApp.",
    solucion: "Centraliza pedidos en un flujo claro para responder más rápido.",
  },
  {
    problema: "Los clientes preguntan constantemente por la carta.",
    solucion: "Comparte tu menú digital mediante QR o enlace.",
  },
  {
    problema: "Pierdes reservas por falta de organización.",
    solucion: "Gestiona reservas y confirmaciones desde el panel.",
  },
  {
    problema: "Actualizar el menú toma demasiado tiempo.",
    solucion: "Edita productos, categorías y disponibilidad en segundos.",
  },
  {
    problema: "No sabes cuáles son tus productos más vendidos.",
    solucion: "Revisa estadísticas claras para tomar mejores decisiones.",
  },
  {
    problema: "Las solicitudes especiales quedan mezcladas con otros mensajes.",
    solucion: "Ordena solicitudes y conviértelas en oportunidades reales.",
  },
];

const funcionCards = [
  {
    title: "Menú Digital QR",
    icon: "bi-qr-code",
    description: "Comparte tu carta mediante un código QR o enlace para que tus clientes puedan verla desde cualquier dispositivo.",
    image: previewCarta,
  },
  {
    title: "Reservas Online",
    icon: "bi-calendar-check",
    description: "Recibe solicitudes de reserva, revisa la información del cliente y organiza confirmaciones desde el panel.",
    image: recursodashboard,
  },
  {
    title: "Pedidos por WhatsApp",
    icon: "bi-whatsapp",
    description: "Permite que tus clientes armen pedidos claros y los envíen por WhatsApp con toda la información ordenada.",
    image: previewWeb,
  },
  {
    title: "Solicitudes Especiales",
    icon: "bi-chat-square-heart",
    description: "Gestiona eventos, cotizaciones, pedidos personalizados y solicitudes fuera de carta sin perder contexto.",
    image: recursodashboard,
  },
  {
    title: "Dashboard Administrativo",
    icon: "bi-speedometer2",
    description: "Centraliza productos, pedidos, reservas, solicitudes y métricas en una vista clara para operar mejor.",
    image: previewPanel,
  },
  {
    title: "Estadísticas",
    icon: "bi-bar-chart",
    description: "Revisa señales clave del negocio como productos más vistos, más vendidos y rendimiento general.",
    image: recursometrica,
  },
  {
    title: "Gestión de Productos",
    icon: "bi-box-seam",
    description: "Crea, edita, destaca y controla la disponibilidad de productos de forma rápida y ordenada.",
    image: recursoproductos,
  },
  {
    title: "Gestión de Categorías",
    icon: "bi-tags",
    description: "Organiza tu menú por categorías para que el cliente encuentre rápido lo que busca.",
    image: recursoproductos,
  },
  {
    title: "Seguimiento de Pedidos",
    icon: "bi-list-check",
    description: "Mantén estados y seguimiento para atender cada solicitud con menos fricción operativa.",
    image: recursodashboard,
  },
  {
    title: "Panel Responsive",
    icon: "bi-phone",
    description: "Administra Menly desde escritorio, tablet o celular con una experiencia adaptable.",
    image: previewPanel,
  },
];

const pasosMenly = [
  {
    titulo: "Crear tu restaurante",
    icono: "bi-shop",
    texto: "Configuramos la base de tu negocio, marca, datos y presencia inicial.",
  },
  {
    titulo: "Configurar menú",
    icono: "bi-card-list",
    texto: "Ordena categorías, productos, precios, fotos y disponibilidad.",
  },
  {
    titulo: "Compartir QR o enlace",
    icono: "bi-qr-code-scan",
    texto: "Publica tu menú en mesas, redes sociales, Google o tu sitio web.",
  },
  {
    titulo: "Recibir actividad",
    icono: "bi-graph-up-arrow",
    texto: "Empieza a recibir reservas, pedidos, solicitudes y datos útiles.",
  },
];

const planes = [
  {
    nombre: "Básico",
    slug: "basico",
    precio: "$24.990",
    texto: "Ideal para comenzar tu presencia digital.",
    url: "https://wa.me/56988424939?text=Hola%2C%20quiero%20informaci%C3%B3n%20sobre%20el%20Plan%20B%C3%A1sico%20de%20Menly",
    items: [
      "Landing web + Menu Digital QR",
      "Carrito de pedidos por WhatsApp",
      "Reservas Online",
      "Gestión completa del menú y productos",
      "Dashboard con estadísticas esenciales",
    ],
  },
  {
    nombre: "Pro",
    slug: "pro",
    precio: "$39.990",
    texto: "Para restaurantes que quieren más control.",
    url: "https://wa.me/56988424939?text=Hola%2C%20quiero%20informaci%C3%B3n%20sobre%20el%20Plan%20Pro%20de%20Menly",
    items: [
      "Todo lo del plan Básico",
      "Seguimiento de pedidos y estados en tiempo real",
      "Dashboard avanzado con métricas y reportes",
      "Solicitudes especiales y gestión completa",
      "Soporte prioritario",
    ],
  },
];

const disenoWeb = [
  {
    titulo: "Landing personalizada",
    icono: "bi-window-sidebar",
    texto: "Diseñamos una página alineada con la identidad de tu restaurante.",
  },
  {
    titulo: "Diseño Responsive",
    icono: "bi-display",
    texto: "Optimizada para celulares, tablets y escritorio.",
  },
  {
    titulo: "SEO",
    icono: "bi-search",
    texto: "Preparada para aparecer en Google.",
  },
  {
    titulo: "Dominio propio",
    icono: "bi-globe2",
    texto: "Publicación bajo un dominio profesional.",
  },
  {
    titulo: "Branding",
    icono: "bi-palette",
    texto: "Colores, fotografías y diseño coherentes con tu marca.",
  },
  {
    titulo: "Optimización móvil",
    icono: "bi-phone",
    texto: "Carga rápida y navegación pensada para dispositivos móviles.",
  },
];

const razonesMenly = [
  {
    icono: "bi-grid-1x2",
    titulo: "Todo en un solo lugar",
    texto: "Gestiona menú, pedidos, reservas, estadísticas y solicitudes desde un único panel.",
  },
  {
    icono: "bi-shop-window",
    titulo: "Pensado para restaurantes",
    texto: "No necesitas conocimientos técnicos para administrar tu restaurante.",
  },
  {
    icono: "bi-layers",
    titulo: "Escalable",
    texto: "Comienza con lo básico y activa nuevas funcionalidades cuando tu negocio crezca.",
  },
];

const preguntasFrecuentes = [
  ["¿Necesito instalar algo?", "No. Menly funciona desde el navegador, sin instalaciones complejas."],
  ["¿Funciona desde el celular?", "Sí. El panel y las páginas están pensados para usarse en celular, tablet y escritorio."],
  ["¿Puedo actualizar mi menú cuando quiera?", "Sí. Puedes editar productos, categorías, precios y disponibilidad desde el panel."],
  ["¿Puedo usar mi propio dominio?", "Sí. Los planes con landing personalizada pueden publicarse bajo un dominio profesional."],
  ["¿Cómo funcionan los pedidos por WhatsApp?", "El cliente arma su pedido y Menly prepara un resumen ordenado para enviarlo por WhatsApp."],
  ["¿Las reservas llegan en tiempo real?", "Las solicitudes quedan registradas para que puedas revisarlas, confirmarlas y gestionarlas."],
  ["¿Qué incluye el soporte?", "Incluye orientación inicial, ayuda de configuración y acompañamiento según el plan contratado."],
  ["¿Puedo cambiar de plan más adelante?", "Sí. Puedes partir con un plan y crecer cuando tu negocio necesite más herramientas."],
  ["¿Hay permanencia mínima?", "No hay contratos de permanencia. Puedes cambiar de plan cuando quieras."],
  ["¿Cómo solicito una demostración?", "Puedes solicitar una demo desde cualquier botón de contacto y coordinamos una revisión guiada."],
];

const recursos = [
  {
    icono: "bi-journal-text",
    titulo: "Guías de uso",
    texto: "Aprende a configurar Menly paso a paso.",
  },
  {
    icono: "bi-life-preserver",
    titulo: "Centro de ayuda",
    texto: "Resuelve tus dudas rápidamente.",
  },
  {
    icono: "bi-stars",
    titulo: "Próximas funcionalidades",
    texto: "Conoce las mejoras que estamos desarrollando.",
  },

  {
    icono: "bi-megaphone",
    titulo: "Actualizaciones",
    texto: "Descubre las novedades de cada versión.",
  },
];

const demos = [
  { nombre: "Bakry Menly", categoria: "Cafe y brunch", url: "https://bakry.menly.cl", img: demobakry },
  { nombre: "Smash House", categoria: "Hamburguesería", url: "https://smash-house.menly.cl", img: demosmash },
  { nombre: "Marea Azul", categoria: "Restaurante", url: "https://marea-azul.menly.cl", img: demosmarea },
];

import recursopizzeria from "../assets/recursopizzeria.png";
import recursopasteleria from "../assets/recursopasteleria.png";
import recursofoodtrucks from "../assets/recursofoodtrucks.png";
import recursobares from "../assets/recursobares.png";
import recursorestaurantes from "../assets/recursorestaurante.png";
const rubrosGastronomicos = [
  ["Cafeterías y Pastelerías","", recursopasteleria],
  ["Restaurantes","", recursorestaurantes],
  ["Food Trucks","", recursofoodtrucks],
  ["Pizzeria","", recursopizzeria],
  ["Bares","", recursobares],
];

const RUBROS_AUTOPLAY_MS = 3600;

const footerLinks = [
  ["Funciones", "funciones"],
  ["Planes", "planes"],
  ["Diseño Web", "diseno-web"],
  ["Recursos", "recursos"],
  ["Contacto", "contacto"],
];

const socialLinks = [
  ["Instagram", "bi-instagram", "#"],
  ["Facebook", "bi-facebook", "#"],
  ["TikTok", "bi-tiktok", "#"],
  ["YouTube", "bi-youtube", "#"],
];

export default function SaberMas() {
  const [openFaq, setOpenFaq] = useState(null);
  const [activeFeature, setActiveFeature] = useState(null);
  const [activeRubro, setActiveRubro] = useState(0);
  const [isRubroInteracting, setIsRubroInteracting] = useState(false);
  const rubroDragStartX = useRef(null);
  const navigate = useNavigate();

  const abrirWhatsApp = (url = WHATSAPP_GENERAL) => {
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const abrirPlan = () => {
    navigate("/planes");
  };
  const scrollToSection = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const cambiarRubro = (direction) => {
    setActiveRubro((current) => {
      const total = rubrosGastronomicos.length;
      return (current + direction + total) % total;
    });
  };

  const obtenerPosicionRubro = (index) => {
    const total = rubrosGastronomicos.length;
    let offset = index - activeRubro;

    if (offset > total / 2) offset -= total;
    if (offset < -total / 2) offset += total;

    return offset;
  };

  const iniciarArrastreRubro = (event) => {
    rubroDragStartX.current = event.clientX;
    setIsRubroInteracting(true);
  };

  const terminarArrastreRubro = (event) => {
    if (rubroDragStartX.current === null) {
      setIsRubroInteracting(false);
      return;
    }

    const deltaX = event.clientX - rubroDragStartX.current;

    if (Math.abs(deltaX) > 42) {
      cambiarRubro(deltaX < 0 ? 1 : -1);
    }

    rubroDragStartX.current = null;
    setIsRubroInteracting(false);
  };

  useEffect(() => {
    if (isRubroInteracting) return undefined;

    const rubrosAutoplay = window.setInterval(() => {
      cambiarRubro(1);
    }, RUBROS_AUTOPLAY_MS);

    return () => window.clearInterval(rubrosAutoplay);
  }, [isRubroInteracting]);

  return (
    <main className="saber-mas-page">
      <PublicNavbar />

      <section className="saber-hero" id="inicio">
        <div className="saber-hero__content">
          <span className="saber-kicker">Menly para restaurantes</span>
          <h1>Digitaliza tu restaurante con una experiencia web completa</h1>
          <p>
            Menly reúne sitio web, menú digital, pedidos por WhatsApp, reservas,
            solicitudes especiales y métricas en una plataforma pensada para negocios
            gastronómicos.
          </p>
          <button type="button" className="saber-primary-btn" onClick={abrirPlan}>
            Solicitar demo
          </button>
        </div>

        <div className="saber-hero__mockup" aria-label="Mockups de Menly">
          <img src={previewPanel} alt="Panel administrativo de Menly" />
          <img src={previewCarta} alt="Menú digital de Menly" />
          <img src={previewWeb} alt="Página web creada con Menly" />
        </div>
      </section>

      <section className="saber-section saber-functions-story" id="funciones">
        <div className="saber-section__heading">
          <span className="saber-kicker">Funciones</span>
          <h2>Menly convierte el caos operativo en un sistema simple</h2>
          <p>
            Antes de hablar de herramientas, hablemos de lo que pasa todos los días
            en un restaurante: mensajes dispersos, reservas sueltas, cartas
            desactualizadas y poca claridad para decidir.
          </p>
        </div>

        <div className="saber-problem-solution">
          <article className="saber-story-panel saber-story-panel--problems">
            <h3>¿Te suena familiar?</h3>
            <ul>
              {problemasSoluciones.map((item) => (
                <li key={item.problema}>
                  <i className="bi bi-x-circle-fill" aria-hidden="true"></i>
                  <span>{item.problema}</span>
                </li>
              ))}
            </ul>
          </article>

          <div className="saber-solution-mockup" aria-label="Dashboard de Menly resolviendo la gestión del restaurante">
            <div className="saber-solution-mockup__halo"></div>
            <img src={recursopersona} alt="Dashboard administrativo de Menly" />
            <div className="saber-solution-chip saber-solution-chip--top">
              <i className="bi bi-lightning-charge-fill" aria-hidden="true"></i>
              Gestión en vivo
            </div>
            <div className="saber-solution-chip saber-solution-chip--bottom">
              <i className="bi bi-check2-circle" aria-hidden="true"></i>
              Todo conectado
            </div>
          </div>

          <article className="saber-story-panel saber-story-panel--solutions">
            <h3>Con Menly, lo solucionas</h3>
            <ul>
              {problemasSoluciones.map((item) => (
                <li key={item.solucion}>
                  <i className="bi bi-check-circle-fill" aria-hidden="true"></i>
                  <span>{item.solucion}</span>
                </li>
              ))}
            </ul>
          </article>
        </div>

        <div className="saber-feature-suite">
          <div className="saber-section__heading saber-section__heading--center">
            <span className="saber-kicker">Todo lo que incluye Menly</span>
            <h2>Funciones diseñadas para vender, ordenar y medir mejor</h2>
          </div>

          <div className="saber-feature-suite__grid">
            {funcionCards.map((funcion, index) => (
              <FeatureFlipCard
                key={funcion.title}
                {...funcion}
                isActive={activeFeature === index}
                onToggle={() => setActiveFeature(activeFeature === index ? null : index)}
                accordionId={`saber-feature-accordion-${index}`}
              />
            ))}
          </div>
        </div>

        <div className="saber-timeline-block">
          <div className="saber-section__heading saber-section__heading--center">
            <span className="saber-kicker">Implementación</span>
            <h2>Así de fácil funciona Menly</h2>
          </div>

          <div className="saber-timeline" aria-label="Pasos para comenzar con Menly">
            {pasosMenly.map((paso, index) => (
              <article className="saber-timeline-step" key={paso.titulo}>
                <div className="saber-timeline-step__number">{index + 1}</div>
                <div className="saber-timeline-step__content">
                  <i className={`bi ${paso.icono}`} aria-hidden="true"></i>
                  <h3>{paso.titulo}</h3>
                  <p>{paso.texto}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="saber-section saber-plans-section" id="planes">
        <div className="saber-section__heading saber-section__heading--center">
          <span className="saber-kicker">Planes</span>
          <h2>Planes que se adaptan a tu restaurante</h2>
          <p>
            Empieza con lo que necesitas y crece cuando tu negocio lo requiera.
          </p>
        </div>

        <div className="saber-plans-grid">
          {planes.map((plan) => (
            <article
              className={`saber-plan-card ${plan.destacado ? "is-featured" : ""}`}
              key={plan.nombre}
            >
              {plan.badge && <span className="saber-plan-badge">{plan.badge}</span>}
              <div className="saber-plan-card__head">
                <h3>Plan {plan.nombre}</h3>
                <p>{plan.texto}</p>
                <div className="saber-plan-price">
                  <span>{plan.precio}</span>
                  <small>/mes</small>
                </div>
              </div>
              <ul>
                {plan.items.map((item) => (
                  <li key={item}>
                    <i className="bi bi-check-circle-fill" aria-hidden="true"></i>
                    {item}
                  </li>
                ))}
              </ul>
              <button type="button" className="saber-primary-btn" onClick={abrirPlan}>
                {plan.destacado ? "Solicitar demo" : "Consultar plan"}
              </button>
            </article>
          ))}
        </div>

        <p className="saber-plan-note">
          Sin contratos de permanencia. Puedes cambiar de plan cuando quieras.
        </p>
      </section>

      <section className="saber-section saber-web-design" id="diseno-web">
        <div className="saber-web-hero">
          <div className="saber-web-hero__copy">
            <span className="saber-kicker">DISEÑO WEB</span>
            <h2>Una landing profesional para hacer crecer tu restaurante.</h2>
            <p>
              Tu restaurante merece una presencia digital profesional. En Menly
              diseñamos páginas rápidas, modernas y optimizadas para convertir
              visitas en reservas, pedidos y nuevos clientes.
            </p>
            <button
              type="button"
              className="saber-primary-btn"
              onClick={() => scrollToSection("demos-web")}
            >
              Ver demos
            </button>
          </div>

          <div className="saber-design-grid">
            {disenoWeb.map((item) => (
              <article className="saber-design-card" key={item.titulo}>
                <span>
                  <i className={`bi ${item.icono}`} aria-hidden="true"></i>
                </span>
                <h3>{item.titulo}</h3>
                <p>{item.texto}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="saber-business-block">
          <div className="saber-section__heading saber-section__heading--center">
            <span className="saber-kicker">Rubros</span>
            <h2>Hecho para cualquier negocio gastronómico</h2>
          </div>

          <div className="saber-business-grid">
            {rubrosGastronomicos.map(([nombre, , imagen], index) => {
              const coverflowPosition = obtenerPosicionRubro(index);

              return (
                <article
                  className={`saber-business-card ${coverflowPosition === 0 ? "is-active" : ""}`}
                  data-coverflow-position={coverflowPosition}
                  key={nombre}
                  onPointerDown={iniciarArrastreRubro}
                  onPointerUp={terminarArrastreRubro}
                  onPointerCancel={() => {
                    rubroDragStartX.current = null;
                    setIsRubroInteracting(false);
                  }}
                >
                  <img src={imagen} alt={`${nombre} con landing Menly`} loading="lazy" />
                  <div>
                    <h3>{nombre}</h3>
                  </div>
                </article>
              );
            })}

            <button
              type="button"
              className="saber-business-nav saber-business-nav--prev"
              aria-label="Ver rubro anterior"
              onClick={() => cambiarRubro(-1)}
              onPointerEnter={() => setIsRubroInteracting(true)}
              onPointerLeave={() => setIsRubroInteracting(false)}
            >
              <i className="bi bi-chevron-left" aria-hidden="true"></i>
            </button>
            <button
              type="button"
              className="saber-business-nav saber-business-nav--next"
              aria-label="Ver rubro siguiente"
              onClick={() => cambiarRubro(1)}
              onPointerEnter={() => setIsRubroInteracting(true)}
              onPointerLeave={() => setIsRubroInteracting(false)}
            >
              <i className="bi bi-chevron-right" aria-hidden="true"></i>
            </button>

            <div className="saber-business-dots" aria-label="Selector de rubros">
              {rubrosGastronomicos.map(([nombre], index) => (
                <button
                  type="button"
                  className={index === activeRubro ? "is-active" : ""}
                  key={nombre}
                  aria-label={`Ver ${nombre}`}
                  aria-current={index === activeRubro ? "true" : undefined}
                  onClick={() => setActiveRubro(index)}
                ></button>
              ))}
            </div>
          </div>
        </div>

        <div className="saber-web-demos" id="demos-web">
          <div className="saber-section__heading saber-section__heading--center">
            <span className="saber-kicker">Demostraciones reales</span>
            <h2>Conoce algunos diseños creados con Menly</h2>
            <p>
              Cada restaurante tiene una identidad diferente. Estas son algunas
              demostraciones.
            </p>
          </div>

          <div className="saber-web-demo-grid">
            {demos.map((demo) => {
              const hasDemo = demo.url && demo.url !== "#";

              return (
                <article className="saber-web-demo-card" key={demo.nombre}>
                  <img src={demo.img} alt={`Captura de la landing ${demo.nombre}`} />
                  <div className="saber-web-demo-card__overlay">
                    <div>
                      <span>{demo.categoria}</span>
                      <h3>{demo.nombre}</h3>
                    </div>
                    <a
                      href={hasDemo ? demo.url : "#demos-web"}
                      target={hasDemo ? "_blank" : undefined}
                      rel={hasDemo ? "noreferrer" : undefined}
                      aria-disabled={!hasDemo}
                    >
                      Ver demo
                    </a>
                  </div>
                </article>
              );
            })}
          </div>
        </div>

      </section>

      <section className="saber-section saber-resources-section saber-section--band" id="recursos">
        <div className="saber-section__heading saber-section__heading--center">
          <span className="saber-kicker">Por qué elegir Menly</span>
          <h2>Una plataforma clara para operar y crecer</h2>
          <p>
            Sin testimonios inventados: preferimos mostrarte razones concretas para
            ordenar tu operación digital.
          </p>
        </div>

        <div className="saber-value-grid">
          {razonesMenly.map((razon) => (
            <article className="saber-value-card" key={razon.titulo}>
              <i className={`bi ${razon.icono}`} aria-hidden="true"></i>
              <h3>{razon.titulo}</h3>
              <p>{razon.texto}</p>
            </article>
          ))}
        </div>

        <div className="saber-faq-block">
          <div className="saber-section__heading saber-section__heading--center">
            <span className="saber-kicker">Dudas frecuentes</span>
            <h2>Preguntas frecuentes</h2>
          </div>

          <div className="saber-faq-list">
            {preguntasFrecuentes.map(([pregunta, respuesta], index) => {
              const isOpen = openFaq === index;
              const panelId = `saber-faq-${index}`;

              return (
                <article className={`saber-faq-item ${isOpen ? "is-open" : ""}`} key={pregunta}>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={panelId}
                    onClick={() => setOpenFaq(openFaq === index ? null : index)}
                  >
                    <span>{pregunta}</span>
                    <i className="bi bi-chevron-down" aria-hidden="true"></i>
                  </button>
                  <div className="saber-faq-panel" id={panelId}>
                    <p>{respuesta}</p>
                  </div>
                </article>
              );
            })}
          </div>
        </div>

        <div className="saber-resource-block">
          <div className="saber-section__heading saber-section__heading--center">
            <span className="saber-kicker">Recursos</span>
            <h2>Recursos para ayudarte a crecer</h2>
          </div>

          <div className="saber-resource-grid">
            {recursos.map((recurso) => (
              <article className="saber-resource-card" key={recurso.titulo}>
                <i className={`bi ${recurso.icono}`} aria-hidden="true"></i>
                <h3>{recurso.titulo}</h3>
                <p>{recurso.texto}</p>
                <button type="button">Ver recurso</button>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="saber-contact-cta" id="contacto">
        <div className="saber-contact-cta__copy">
          <span className="saber-kicker">Contacto</span>
          <h2>¿Listo para digitalizar tu negocio?</h2>
          <p>
            Solicita una demostración gratuita y descubre cómo Menly puede ayudarte a
            gestionar tu restaurante de forma más simple.
          </p>
        </div>

        <div className="saber-contact-cta__actions">
          <button type="button" className="saber-primary-btn" onClick={abrirPlan}>
            Solicitar demo gratuita
          </button>
          <a className="saber-secondary-action" href={WHATSAPP_GENERAL} target="_blank" rel="noreferrer">
            Hablar por WhatsApp
          </a>
        </div>
      </section>

      <footer className="saber-footer">
        <div className="saber-footer__brand">
          <img src={logoMenly} alt="Menly" />
          <div>
            <strong>Menly</strong>
            <p>© 2026 Menly. Todos los derechos reservados.</p>
          </div>
        </div>

        <nav className="saber-footer__links" aria-label="Navegación de pie de página">
          {footerLinks.map(([label, sectionId]) => (
            <button type="button" key={sectionId} onClick={() => scrollToSection(sectionId)}>
              {label}
            </button>
          ))}
        </nav>

        <div className="saber-footer__social" aria-label="Redes sociales">
          {socialLinks.map(([label, icon, href]) => (
            <a key={label} href={href} aria-label={label}>
              <i className={`bi ${icon}`} aria-hidden="true"></i>
            </a>
          ))}
        </div>
      </footer>
    </main>
  );
}
