const CACHE = 'tennis-analyst-v4';
const STATIC = ['/style.css', '/script.js', '/manifest.json', '/icon.svg', '/logo.svg'];

// Cache static assets on install
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
  self.skipWaiting();
});

// Remove old caches on activate
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const { pathname } = new URL(event.request.url);

  // Never intercept API calls
  if (pathname.startsWith('/api/')) return;

  // Cache-first for static assets (CSS, JS, icons)
  if (STATIC.includes(pathname)) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
    return;
  }

  // Network-first for HTML pages (auth state must stay accurate)
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
