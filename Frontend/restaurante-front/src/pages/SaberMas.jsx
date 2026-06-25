import "bootstrap-icons/font/bootstrap-icons.css";
import "../styles/SaberMas.css";
import logoMenly from "../assets/logoMenly2.png";
import demosmash from "../assets/demo-smash-house.png";
import demobakry from "../assets/demo-bakry.png";
import demosmarea from "../assets/demo-marea-azul.png"
import previewPanel from "../assets/recursologin1.png";
import previewCarta from "../assets/recursologin3.png";
import previewWeb from "../assets/recursologin2.png";
import recursometrica from "../assets/recursometrica.png";
import recursodashboard from "../assets/recursodashboard.png";
import recursoproductos from "../assets/recursoproductos.png";
import fotoBowl from "../assets/Bowl_de_salteado_colorido_y_sabroso-removebg-preview.png";
import fotoVegetales from "../assets/Ilustración minimalista de vegetales.png";

const WHATSAPP_GENERAL =
  "https://wa.me/56988424939?text=Hola%2C%20quiero%20saber%20m%C3%A1s%20sobre%20Menly";
const LOGIN_URL = "https://menly.cl/";

const fotos = [
  { src: recursometrica, alt: "Panel de Metricas" },
  { src: recursodashboard, alt: "Panel principal" },
  { src: recursoproductos, alt: "Panel productos" },
  { src: previewCarta, alt: "Vista de menu digital Menly" },
];

const sobreCards = [
  ["Todo en un solo lugar", "Carta, pedidos, reservas y gestion reunidos en una experiencia clara."],
  ["Facil de administrar", "Actualiza productos, horarios e informacion sin depender de terceros."],
  ["Pensado para negocios gastronomicos", "Restaurantes, cafeterias, foodtrucks y pastelerias pueden partir rapido."],
  ["Acompanamiento inicial", "Te ayudamos a ordenar el primer paso para salir con una presencia profesional."],
];

const funcionalidades = [
  ["bi-qr-code", "Menu digital con QR", "Tus clientes ven la carta desde el celular, sin esperas ni archivos pesados."],
  ["bi-whatsapp", "Pedidos por WhatsApp", "Recibe pedidos con resumen claro y contacto directo con el cliente."],
  ["bi-calendar-check", "Reservas online", "Organiza solicitudes de reserva desde una pagina simple y disponible."],
  ["bi-globe2", "Pagina web propia", "Un espacio web para mostrar tu marca, fotos, ubicacion y horarios."],
  ["bi-kanban", "Panel de administracion", "Controla productos, pedidos, reservas y configuracion desde el panel."],
  ["bi-bar-chart", "Metricas y reportes", "Consulta datos basicos o reportes mas completos segun tu plan."],
];

const beneficios = [
  "Mas orden para el local",
  "Mejor experiencia para el cliente",
  "No depende solo de Instagram",
  "Diseno adaptado a la marca del negocio",
  "Ideal para restaurantes, cafeterias, foodtrucks y pastelerias",
];

const demos = [
  { nombre: "Bakry Menly", url: "https://bakry.menly.cl", img: demobakry },
  { nombre: "Smash House", url: "https://smash-house.menly.cl", img: demosmash },
  { nombre: "Marea Azul", url: "https://marea-azul.menly.cl", img: demosmarea },
];

const planes = [
  {
    nombre: "Basico",
    texto: "Ideal para comenzar a digitalizar tu local.",
    url: "https://wa.me/56988424939?text=Hola%2C%20quiero%20informaci%C3%B3n%20sobre%20el%20Plan%20B%C3%A1sico%20de%20Menly",
    items: [
      "Menu digital",
      "Pagina web basica",
      "Pedidos por WhatsApp",
      "Reservas online opcionales",
      "Soporte inicial",
    ],
  },
  {
    nombre: "Pro",
    texto: "Para locales que quieren mas control, mejor gestion y crecimiento.",
    url: "https://wa.me/56988424939?text=Hola%2C%20quiero%20informaci%C3%B3n%20sobre%20el%20Plan%20Pro%20de%20Menly",
    destacado: true,
    items: [
      "Todo lo del plan Basico",
      "Panel de administracion completo",
      "Metricas y reportes",
      "Gestion avanzada de productos",
      "Personalizacion visual superior",
      "Soporte prioritario",
    ],
  },
];

export default function SaberMas() {
  const abrirWhatsApp = (url = WHATSAPP_GENERAL) => {
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const irADemos = () => {
    document.getElementById("demos")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <main className="saber-mas-page">
      <section className="saber-hero">
        <nav className="saber-nav" aria-label="Menly">
          <img src={logoMenly} alt="Menly" />
          <div className="saber-nav-actions">
            <a className="saber-login-link" href={LOGIN_URL}>
              LOGIN
            </a>
            <button type="button" onClick={() => abrirWhatsApp()}>
              Contactanos por WhatsApp
            </button>
          </div>
        </nav>

        <div className="saber-hero-content">
          <div>
            <span className="saber-kicker">Menly para restaurantes</span>
            <h1>Conoce como Menly puede ayudar a tu restaurante</h1>
            <p>
              Una plataforma para digitalizar tu carta, recibir pedidos por WhatsApp,
              gestionar reservas y mostrar tu negocio de forma profesional.
            </p>
            <div className="saber-hero-actions">
              <button type="button" onClick={() => abrirWhatsApp()}>
                Contactanos por WhatsApp
              </button>
              <button type="button" className="saber-secondary-btn" onClick={irADemos}>
                Ver demos
              </button>
            </div>
          </div>

          <div className="saber-hero-preview" aria-label="Vistas de Menly">
            <img src={previewPanel} alt="Panel administrativo de Menly" />
            <img src={previewCarta} alt="Menu digital de Menly" />
          </div>
        </div>
      </section>

      <section className="saber-section saber-two-columns">
        <div>
          <span className="saber-kicker">Sobre Menly</span>
          <h2>Sobre Menly</h2>
          <p>
            Menly es una plataforma pensada para restaurantes, cafeterias, foodtrucks
            y negocios gastronomicos que quieren ordenar su presencia digital,
            mejorar la experiencia del cliente y vender mas desde una pagina simple,
            moderna y facil de administrar.
          </p>
        </div>
        <div className="saber-card-grid">
          {sobreCards.map(([titulo, texto]) => (
            <article className="saber-card" key={titulo}>
              <h3>{titulo}</h3>
              <p>{texto}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="saber-section">
        <div className="saber-section-heading">
          <span className="saber-kicker">Galeria</span>
          <h2>Fotos</h2>
        </div>
        <div className="saber-photo-grid">
          {fotos.map((foto) => (
            <img key={foto.alt} src={foto.src} alt={foto.alt} />
          ))}
        </div>
      </section>

      <section className="saber-section">
        <div className="saber-section-heading">
          <span className="saber-kicker">Funcionalidades</span>
          <h2>Que hace Menly</h2>
        </div>
        <div className="saber-feature-grid">
          {funcionalidades.map(([icono, titulo, texto]) => (
            <article className="saber-card saber-feature-card" key={titulo}>
              <i className={`bi ${icono}`} aria-hidden="true"></i>
              <h3>{titulo}</h3>
              <p>{texto}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="saber-section saber-benefits">
        <div className="saber-section-heading">
          <span className="saber-kicker">Beneficios</span>
          <h2>Por que elegir Menly?</h2>
        </div>
        <ul>
          {beneficios.map((beneficio) => (
            <li key={beneficio}>
              <i className="bi bi-check2-circle" aria-hidden="true"></i>
              {beneficio}
            </li>
          ))}
        </ul>
      </section>

      <section className="saber-section" id="demos">
        <div className="saber-section-heading">
          <span className="saber-kicker">Referencias</span>
          <h2>Demos</h2>
        </div>
        <div className="saber-demo-grid">
          {demos.map((demo) => (
            <article className="saber-card saber-demo-card" key={demo.nombre}>
              <img src={demo.img} alt={`Preview ${demo.nombre}`} />
              <h3>{demo.nombre}</h3>
              <a
                href={demo.url}
                target={demo.url === "#" ? undefined : "_blank"}
                rel={demo.url === "#" ? undefined : "noreferrer"}
              >
                Ver demo
              </a>
            </article>
          ))}
        </div>
      </section>

      <section className="saber-section">
        <div className="saber-section-heading">
          <span className="saber-kicker">Planes</span>
          <h2>Planes</h2>
        </div>
        <div className="saber-plans-grid">
          {planes.map((plan) => (
            <article
              className={`saber-plan-card ${plan.destacado ? "is-featured" : ""}`}
              key={plan.nombre}
            >
              <span>{plan.nombre}</span>
              <p>{plan.texto}</p>
              <ul>
                {plan.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <button type="button" onClick={() => abrirWhatsApp(plan.url)}>
                Quiero este plan
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="saber-final-cta">
        <span className="saber-kicker">Empecemos</span>
        <h2>Listo para digitalizar tu negocio?</h2>
        <p>Conversemos por WhatsApp y veamos como Menly puede adaptarse a tu local.</p>
        <button type="button" onClick={() => abrirWhatsApp()}>
          Contactanos por WhatsApp
        </button>
      </section>
    </main>
  );
}
