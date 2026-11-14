"use strict";
const CACHE = "aranko-shell-v3";
const SHELL = [
  "/static/icons/aranko.svg",
  "/static/icons/aranko-180.png",
  "/static/icons/aranko-192.png",
  "/static/icons/aranko-512.png",
  "/static/manifest.json",
  "/static/app.css",
  "/static/app.js",
  "/static/pwa.js",
  "/static/vendor/jspdf.umd.min.js",
  "/static/vendor/jspdf.plugin.autotable.min.js"
];
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
  }
});
