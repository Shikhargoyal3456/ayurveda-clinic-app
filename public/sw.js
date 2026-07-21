const CACHE_NAME = "kash-ai-v1";
const STATIC_ASSETS = [
  "/",
  "/login",
  "/auth/login",
  "/public/manifest.json",
  "/static/css/style.min.css",
  "/static/css/neuralink.css",
  "/static/js/script.js",
  "/static/js/pwa.js",
  "/shared-static/css/variables.css",
  "/shared-static/css/components.css",
  "/shared-static/css/utilities.css",
  "/shared-static/css/layouts.css",
  "/shared-static/css/modern.css",
  "/shared-static/css/responsive.css"
];

async function openOfflineDb() {
  return await new Promise((resolve, reject) => {
    const request = indexedDB.open("kash-ai-offline", 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("offlineQueue")) {
        db.createObjectStore("offlineQueue", { keyPath: "id", autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function queueFailedRequest(request) {
  const cloned = request.clone();
  const bodyText = await cloned.text();
  const db = await openOfflineDb();
  const tx = db.transaction("offlineQueue", "readwrite");
  tx.objectStore("offlineQueue").add({
    url: request.url,
    method: request.method,
    headers: Array.from(request.headers.entries()),
    bodyText,
    createdAt: new Date().toISOString()
  });
  return await tx.complete;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => undefined)
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method === "GET" && (request.destination || "").match(/style|script|image|font|document/)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) {
          return cached;
        }
        return fetch(request).then((response) => {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, cloned)).catch(() => undefined);
          return response;
        });
      })
    );
    return;
  }

  if (url.pathname.startsWith("/api/") || request.method !== "GET") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (request.method === "GET" && response.ok) {
            const cloned = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, cloned)).catch(() => undefined);
          }
          return response;
        })
        .catch(async () => {
          if (request.method !== "GET") {
            await queueFailedRequest(request);
            return new Response(
              JSON.stringify({ success: false, queued: true, message: "Saved offline. It will sync when you reconnect." }),
              { headers: { "Content-Type": "application/json" }, status: 202 }
            );
          }
          const cached = await caches.match(request);
          return cached || new Response(JSON.stringify({ success: false, offline: true }), { headers: { "Content-Type": "application/json" }, status: 503 });
        })
    );
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        const cloned = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, cloned)).catch(() => undefined);
        return response;
      })
      .catch(() => caches.match(request).then((cached) => cached || caches.match("/")))
  );
});

self.addEventListener("message", async (event) => {
  if (event.data?.type === "GET_QUEUE_COUNT") {
    const db = await openOfflineDb();
    const tx = db.transaction("offlineQueue", "readonly");
    const countRequest = tx.objectStore("offlineQueue").count();
    countRequest.onsuccess = () => {
      event.source?.postMessage({ type: "QUEUE_COUNT", count: countRequest.result || 0 });
    };
  }
});
