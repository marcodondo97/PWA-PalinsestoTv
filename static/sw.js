const CACHE_NAME = 'palinsesto-tv-v2';
const APP_SHELL = [
  '/',
  '/static/css/styles.css',
  '/static/icons/favicon.svg',
  '/static/icons/favicon-96x96.png',
  '/static/icons/web-app-manifest-192x192.png',
  '/static/icons/web-app-manifest-512x512.png',
  '/manifest.webmanifest'
];

function shouldCache(request) {
  const url = new URL(request.url);
  
  if (url.protocol === 'chrome-extension:' || 
      url.protocol === 'chrome-devtools:' ||
      url.protocol === 'moz-extension:' ||
      url.protocol === 'edge-extension:') {
    return false;
  }
  
  if (url.protocol !== 'https:' && url.protocol !== 'http:') {
    return false;
  }
  
  if (request.method !== 'GET') {
    return false;
  }
  
  return true;
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  
  if (!shouldCache(request)) {
    return;
  }
  
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          if (res && res.status === 200) {
            const resClone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, resClone));
          }
          return res;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }
      
      return fetch(request).then((res) => {
        if (res && res.status === 200) {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, resClone));
        }
        return res;
      }).catch(() => {
        if (request.destination === 'image') {
          return caches.match('/static/icons/favicon.svg');
        }
        return new Response('Network error', { status: 503 });
      });
    })
  );
});


