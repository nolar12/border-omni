/// <reference lib="webworker" />
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';

declare const self: ServiceWorkerGlobalScope;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event: ExtendableEvent) => {
  event.waitUntil(self.clients.claim());
});

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// ─── Share Target ─────────────────────────────────────────────────────────────
// Intercepts POST from the OS share sheet and stores files in Cache,
// then redirects the browser to /share where the React app picks them up.

const SHARE_CACHE = 'share-target-v1';

self.addEventListener('fetch', (event: FetchEvent) => {
  const url = new URL(event.request.url);
  if (url.pathname === '/share-target' && event.request.method === 'POST') {
    event.respondWith(handleShare(event.request));
  }
});

async function handleShare(request: Request): Promise<Response> {
  const cache = await caches.open(SHARE_CACHE);
  try {
    const formData = await request.formData();
    const files = formData.getAll('files') as File[];

    // Clear previous pending shares
    const keys = await cache.keys();
    await Promise.all(keys.map(k => cache.delete(k)));

    // Store each file as a cache entry with a synthetic URL
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      await cache.put(
        `/share-file-${i}`,
        new Response(file, {
          headers: {
            'Content-Type': file.type,
            'X-File-Name': encodeURIComponent(file.name),
          },
        }),
      );
    }
    // Store metadata
    await cache.put(
      '/share-meta',
      new Response(JSON.stringify({ count: files.length }), {
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  } catch {
    // ignore errors — just redirect with empty queue
  }
  return Response.redirect('/share', 303);
}
