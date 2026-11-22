'use strict';

const CACHE_NAME = 'destination-images-v1';

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
    );

    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
        const keys = await caches.keys();

        await Promise.all(
            keys
                .filter((key) =>
                    key.startsWith('destination-images-') &&
                    key !== CACHE_NAME
                )
                .map((key) => caches.delete(key))
        );

        await self.clients.claim();
    })());
});

self.addEventListener('fetch', (event) => {
    const request = event.request;

    if (
        request.method !== 'GET' ||
        request.destination !== 'image'
    ) {
        return;
    }

    const url = new URL(request.url);

    if (url.protocol !== 'https:' && url.hostname !== 'localhost') {
        return;
    }

    event.respondWith((async () => {
        const cache = await caches.open(CACHE_NAME);
        const cached = await cache.match(request);

        if (cached) {
            return cached;
        }

        try {
            const response = await fetch(request);

            if (
                response.ok &&
                (response.type === 'basic' || response.type === 'cors')
            ) {
                await cache.put(request, response.clone());
            }

            return response;
        } catch {
            return new Response('', {
                status: 503,
                statusText: 'Image unavailable offline'
            });
        }
    })());
});
