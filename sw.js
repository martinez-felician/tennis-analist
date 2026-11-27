const CACHE = 'tennis-analyst-v9';
const STATIC = ['/style.css', '/script.js', '/fonts.css', '/vendor/chart.umd.min.js', '/fonts/dm-sans-latin-400-normal.woff2', '/fonts/dm-sans-latin-500-normal.woff2', '/fonts/dm-sans-latin-600-normal.woff2', '/fonts/dm-sans-latin-700-normal.woff2', '/fonts/dm-serif-display-latin-400-normal.woff2', '/i18n.js', '/i18n-es.js', '/manifest.json', '/icon.svg', '/logo.svg', '/icon-192.png', '/icon-512.png', '/icon-180.png'];

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
