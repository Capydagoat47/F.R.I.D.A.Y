const CACHE_NAME = "friday-hud-v1";
const APP_SHELL = [
  "/",
  "/index.html",
  "/app.css",
  "/app.js",
  "/manifest.json",
  "/icons/friday-icon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== "GET") {
    return;
  }

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(request).catch(() => new Response(JSON.stringify({
      ok: false,
      offline: true,
      reply: "FRIDAY offline shell is active. Reconnect the local server for live AI and telemetry.",
    }), {
      status: 503,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    })));
    return;
  }

  event.respondWith(
    caches.match(request)
      .then((cached) => cached || fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      }))
      .catch(() => caches.match("/")),
  );
});
