const CACHE_NAME = "mte-cache-v1";
const ASSETS = ["/", "/index.html", "/script_v2.js", "/styles.css", "/manifest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (ASSETS.includes(url.pathname)) {
    e.respondWith(caches.match(e.request).then(res => res || fetch(e.request)));
  }
  // API calls go directly to network
});




















