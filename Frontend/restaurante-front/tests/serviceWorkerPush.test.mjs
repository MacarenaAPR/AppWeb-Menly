import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";


const serviceWorkerSource = fs.readFileSync(
  new URL("../public/sw.js", import.meta.url),
  "utf8",
);

const crearRuntime = (windowClients = []) => {
  const listeners = {};
  const notificaciones = [];
  const self = {
    location: { origin: "https://menly.cl" },
    addEventListener: (type, callback) => {
      listeners[type] = callback;
    },
    skipWaiting: () => Promise.resolve(),
    clients: {
      claim: () => Promise.resolve(),
      matchAll: async () => windowClients,
      openWindow: async (url) => ({ url }),
    },
    registration: {
      showNotification: async (title, options) => {
        notificaciones.push({ title, options });
      },
    },
  };

  vm.runInNewContext(serviceWorkerSource, { self, URL });
  return { listeners, notificaciones };
};

const ejecutarEvento = async (listener, event) => {
  let pending;
  listener({
    ...event,
    waitUntil: (promise) => {
      pending = promise;
    },
  });
  await pending;
};

const payloadPedido = {
  title: "Nuevo pedido",
  body: "Ha llegado un nuevo pedido de WhatsApp.",
  pedido_id: 123,
  url: "/dashboard/restaurante/pedidos",
  tag: "pedido-whatsapp-123",
};

test("muestra Web Push y marca el pedido si Pedidos no esta visible", async () => {
  const mensajes = [];
  const client = {
    url: "https://menly.cl/dashboard/restaurante/pedidos",
    visibilityState: "hidden",
    postMessage: (mensaje) => mensajes.push(mensaje),
  };
  const runtime = crearRuntime([client]);

  await ejecutarEvento(runtime.listeners.push, {
    data: { json: () => payloadPedido },
  });

  assert.equal(runtime.notificaciones.length, 1);
  assert.equal(runtime.notificaciones[0].title, "Nuevo pedido");
  assert.equal(runtime.notificaciones[0].options.tag, "pedido-whatsapp-123");
  assert.equal(runtime.notificaciones[0].options.requireInteraction, true);
  assert.equal(mensajes.length, 1);
  assert.equal(mensajes[0].type, "MENLY_PUSH_NOTIFICADO");
  assert.equal(mensajes[0].pedido_id, 123);
});

test("deja el aviso al MP3 si la pantalla de Pedidos esta visible", async () => {
  const client = {
    url: "https://menly.cl/dashboard/restaurante/pedidos",
    visibilityState: "visible",
    postMessage: () => assert.fail("No debe marcar como notificado un pedido visible"),
  };
  const runtime = crearRuntime([client]);

  await ejecutarEvento(runtime.listeners.push, {
    data: { json: () => payloadPedido },
  });

  assert.equal(runtime.notificaciones.length, 0);
});

test("el clic reutiliza una ventana y navega a Pedidos", async () => {
  let destinoNavegado = "";
  let enfocada = false;
  const client = {
    url: "https://menly.cl/dashboard/restaurante/configuracion",
    visibilityState: "hidden",
    postMessage: () => {},
    navigate: async (url) => {
      destinoNavegado = url;
      return client;
    },
    focus: async () => {
      enfocada = true;
      return client;
    },
  };
  const runtime = crearRuntime([client]);
  let cerrada = false;

  await ejecutarEvento(runtime.listeners.notificationclick, {
    notification: {
      data: { url: payloadPedido.url, pedido_id: 123 },
      close: () => {
        cerrada = true;
      },
    },
  });

  assert.equal(cerrada, true);
  assert.equal(destinoNavegado, `https://menly.cl${payloadPedido.url}`);
  assert.equal(enfocada, true);
});
