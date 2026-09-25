const CACHE_NAME = 'spyteam-pwa-v4-avatar';

const STATIC_ASSETS = [
    '/static/offline.html',
    '/static/css/style.css',
    '/static/js/security.js',
    '/static/js/pwa.js',
    '/static/img/logo-spy-team.svg',
    '/static/img/favicon-spyteam.svg',
    '/static/img/pwa-192.png',
    '/static/img/pwa-512.png',
    '/static/img/pwa-maskable-512.png',
    '/static/img/notification-icon-192.png',
    '/static/img/notification-badge-96.png'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys()
            .then(keys => Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            ))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    const request = event.request;

    if (request.method !== 'GET') return;

    const url = new URL(request.url);

    // Nunca colocamos APIs nem páginas autenticadas em cache.
    if (url.origin === self.location.origin && url.pathname.startsWith('/api/')) {
        return;
    }

    // Navegação: rede primeiro. Se estiver offline, exibe uma página neutra.
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request).catch(() => caches.match('/static/offline.html'))
        );
        return;
    }

    // CSS e JavaScript: rede primeiro. Isso evita que uma atualização do
    // aplicativo continue usando estilos ou scripts antigos depois de um deploy.
    if (url.origin === self.location.origin && (
        url.pathname.startsWith('/static/js/') ||
        url.pathname.startsWith('/static/css/')
    )) {
        event.respondWith((async () => {
            const cache = await caches.open(CACHE_NAME);

            try {
                const response = await fetch(request);

                if (response && response.ok) {
                    await cache.put(request, response.clone());
                }

                return response;
            } catch (_) {
                return await cache.match(request, { ignoreSearch: true });
            }
        })());
        return;
    }

    // Demais arquivos estáticos: cache com atualização em segundo plano.
    if (url.origin === self.location.origin && (
        url.pathname.startsWith('/static/') ||
        url.pathname === '/manifest.webmanifest'
    )) {
        event.respondWith((async () => {
            const cache = await caches.open(CACHE_NAME);
            const cached = await cache.match(request, { ignoreSearch: true });

            const networkPromise = fetch(request)
                .then(response => {
                    if (response && response.ok) {
                        cache.put(request, response.clone());
                    }
                    return response;
                })
                .catch(() => cached);

            return cached || networkPromise;
        })());
    }
});

self.addEventListener('push', event => {
    let dados = {};

    try {
        dados = event.data ? event.data.json() : {};
    } catch (_) {
        dados = {
            title: 'SPY TEAM',
            body: event.data ? event.data.text() : 'Você tem uma nova atualização.'
        };
    }

    const titulo = dados.title || 'SPY TEAM';

    const opcoes = {
        body: dados.body || 'Você tem uma nova atualização.',
        icon: dados.icon || '/static/img/notification-icon-192.png',
        badge: dados.badge || '/static/img/notification-badge-96.png',
        tag: dados.tag || 'spyteam',
        renotify: true,
        data: {
            url: dados.url || '/aluno'
        }
    };

    event.waitUntil(
        self.registration.showNotification(titulo, opcoes)
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();

    const destino = new URL(
        event.notification?.data?.url || '/aluno',
        self.location.origin
    ).href;

    event.waitUntil((async () => {
        const janelas = await self.clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        });

        for (const janela of janelas) {
            if ('navigate' in janela) {
                await janela.navigate(destino);
            }

            if ('focus' in janela) {
                return janela.focus();
            }
        }

        return self.clients.openWindow(destino);
    })());
});
