/* YAP service worker — makes the app installable and usable offline (shell only).
   Network-first for the app shell so updates always load when online; API is never cached.
   Bump CACHE to force clients onto a new version. */
const CACHE = "yap-v1";
const SHELL = ["/", "/app.js", "/styles.css", "/manifest.json", "/icon-192.png"];

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL).catch(() => {})));
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api")) return; // API -> straight to network
  e.respondWith((async () => {
    try {
      const res = await fetch(e.request);
      const c = await caches.open(CACHE);
      c.put(e.request, res.clone()).catch(() => {});
      return res;
    } catch (_) {
      return (await caches.match(e.request)) || (await caches.match("/"));
    }
  })());
});
