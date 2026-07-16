self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  const payloadPredeterminado = {
    type: "nuevo_pedido",
    title: "Nuevo pedido",
    body: "Ha llegado un nuevo pedido de WhatsApp.",
    url: "/",
    tag: "nuevo-pedido",
  };
  let payload = payloadPredeterminado;

  try {
    payload = { ...payloadPredeterminado, ...(event.data?.json() || {}) };
  } catch {
    payload = payloadPredeterminado;
  }

  event.waitUntil((async () => {
    const windowClients = await self.clients.matchAll({
      type: "window",
      includeUncontrolled: true,
    });
    const destino = new URL(payload.url || "/", self.location.origin);
    const pedidosVisible = windowClients.some((client) => {
      const clientUrl = new URL(client.url);
      return client.visibilityState === "visible" && clientUrl.pathname === destino.pathname;
    });

    if (pedidosVisible) return;

    windowClients.forEach((client) => {
      client.postMessage({
        type: "MENLY_PUSH_NOTIFICADO",
        pedido_id: payload.pedido_id,
      });
    });

    await self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/icons/launchericon-192x192.png",
      badge: "/icons/launchericon-72x72.png",
      tag: payload.tag,
      renotify: true,
      requireInteraction: true,
      data: {
        url: destino.pathname + destino.search + destino.hash,
        pedido_id: payload.pedido_id,
      },
    });
  })());
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destino = new URL(event.notification.data?.url || "/", self.location.origin);

  event.waitUntil((async () => {
    const windowClients = await self.clients.matchAll({
      type: "window",
      includeUncontrolled: true,
    });
    const clientExacto = windowClients.find((client) => {
      const clientUrl = new URL(client.url);
      return clientUrl.pathname === destino.pathname;
    });
    const client = clientExacto || windowClients[0];

    if (client) {
      if (new URL(client.url).pathname !== destino.pathname && "navigate" in client) {
        const clientNavegado = await client.navigate(destino.href);
        return (clientNavegado || client).focus();
      }
      return client.focus();
    }

    return self.clients.openWindow(destino.href);
  })());
});
