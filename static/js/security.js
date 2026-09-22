// ============================================================
// SECURITY.JS
// Proteção CSRF automática para chamadas mutáveis da API.
// ============================================================

(function () {
    'use strict';

    const CSRF_COOKIE = 'spyteam_csrf';
    const CSRF_HEADER = 'X-CSRF-Token';
    const MUTABLE_METHODS = new Set([
        'POST', 'PUT', 'PATCH', 'DELETE'
    ]);

    function lerCookie(nome) {
        const prefixo = `${nome}=`;

        for (const parte of document.cookie.split(';')) {
            const cookie = parte.trim();

            if (cookie.startsWith(prefixo)) {
                return decodeURIComponent(
                    cookie.substring(prefixo.length)
                );
            }
        }

        return null;
    }

    const fetchOriginal = window.fetch.bind(window);

    window.fetch = function (recurso, opcoes = {}) {
        const metodo = String(
            opcoes.method ||
            (recurso instanceof Request ? recurso.method : 'GET')
        ).toUpperCase();

        let url;

        try {
            url = new URL(
                recurso instanceof Request ? recurso.url : recurso,
                window.location.href
            );
        } catch (_) {
            return fetchOriginal(recurso, opcoes);
        }

        const mesmaOrigem =
            url.origin === window.location.origin;

        const deveProteger =
            mesmaOrigem &&
            url.pathname.startsWith('/api/') &&
            MUTABLE_METHODS.has(metodo);

        if (!deveProteger) {
            return fetchOriginal(recurso, opcoes);
        }

        const token = lerCookie(CSRF_COOKIE);
        const headers = new Headers(
            opcoes.headers ||
            (recurso instanceof Request ? recurso.headers : undefined)
        );

        if (token) {
            headers.set(CSRF_HEADER, token);
        }

        const novasOpcoes = {
            ...opcoes,
            headers
        };

        return fetchOriginal(recurso, novasOpcoes);
    };
})();
