// ============================================================
// PWA.JS
// Instalação do SPY TEAM + Web Push
// ============================================================

(function () {
    'use strict';

    let installPrompt = null;

    function standalone() {
        return window.matchMedia('(display-mode: standalone)').matches ||
            window.navigator.standalone === true;
    }

    function ehIOS() {
        return /iphone|ipad|ipod/i.test(navigator.userAgent);
    }

    function texto(id, valor, classe) {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = valor;
        if (classe) el.dataset.state = classe;
    }

    async function registrarServiceWorker() {
        if (!('serviceWorker' in navigator)) return null;

        try {
            await navigator.serviceWorker.register('/service-worker.js', {
                scope: '/'
            });
            return await navigator.serviceWorker.ready;
        } catch (erro) {
            console.error('[SpyTeam PWA] Falha ao registrar service worker:', erro);
            return null;
        }
    }

    function atualizarEstadoInstalacao() {
        const botao = document.getElementById('btnInstalarPwa');
        const status = document.getElementById('pwaInstallStatus');
        const dica = document.getElementById('pwaInstallHint');

        if (!botao && !status && !dica) return;

        if (standalone()) {
            if (botao) botao.hidden = true;
            if (status) status.textContent = 'SPY TEAM instalado neste dispositivo.';
            if (dica) dica.textContent = 'Você está usando a versão instalada.';
            return;
        }

        if (botao) botao.hidden = !installPrompt;

        if (status) {
            status.textContent = installPrompt
                ? 'Aplicativo pronto para instalar.'
                : 'Você está usando o SPY TEAM pelo navegador.';
        }

        if (dica) {
            if (ehIOS()) {
                dica.textContent = 'No iPhone/iPad: Compartilhar → Adicionar à Tela de Início.';
            } else if (!installPrompt) {
                dica.textContent = 'Quando o navegador liberar a instalação, o botão aparecerá aqui.';
            } else {
                dica.textContent = 'Instale para abrir em tela cheia como aplicativo.';
            }
        }
    }

    window.addEventListener('beforeinstallprompt', event => {
        event.preventDefault();
        installPrompt = event;
        atualizarEstadoInstalacao();
    });

    window.addEventListener('appinstalled', () => {
        installPrompt = null;
        atualizarEstadoInstalacao();
    });

    async function instalarPwa() {
        if (!installPrompt) return;

        installPrompt.prompt();

        try {
            await installPrompt.userChoice;
        } finally {
            installPrompt = null;
            atualizarEstadoInstalacao();
        }
    }

    function urlBase64ParaUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');
        const raw = window.atob(base64);
        return Uint8Array.from([...raw].map(char => char.charCodeAt(0)));
    }

    async function obterRegistro() {
        if (!('serviceWorker' in navigator)) return null;
        return await navigator.serviceWorker.ready;
    }

    async function obterConfigPush() {
        const resposta = await fetch('/api/push/config');

        if (resposta.status === 401) {
            return null;
        }

        if (!resposta.ok) {
            throw new Error('Não foi possível carregar a configuração de notificações.');
        }

        return await resposta.json();
    }

    async function assinaturaAtual() {
        const registro = await obterRegistro();
        if (!registro || !registro.pushManager) return null;
        return await registro.pushManager.getSubscription();
    }

    async function sincronizarAssinaturaComServidor(subscription) {
        const json = subscription.toJSON();

        const resposta = await fetch('/api/push/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                endpoint: subscription.endpoint,
                keys: {
                    p256dh: json.keys?.p256dh || '',
                    auth: json.keys?.auth || ''
                }
            })
        });

        if (!resposta.ok) {
            const dados = await resposta.json().catch(() => ({}));
            throw new Error(dados.detail || 'Não foi possível salvar a assinatura.');
        }
    }

    async function atualizarEstadoNotificacoes() {
        const botao = document.getElementById('btnNotificacoesPwa');
        const teste = document.getElementById('btnTesteNotificacaoPwa');
        const status = document.getElementById('pwaNotificationStatus');

        if (!botao && !status) return;

        if (!('Notification' in window) || !('PushManager' in window)) {
            if (botao) botao.disabled = true;
            if (teste) teste.hidden = true;
            if (status) status.textContent = 'Este navegador não oferece Web Push.';
            return;
        }

        if (ehIOS() && !standalone()) {
            if (botao) {
                botao.disabled = true;
                botao.textContent = 'Instale o app primeiro';
            }
            if (teste) teste.hidden = true;
            if (status) status.textContent = 'No iPhone/iPad, instale o SPY TEAM na Tela de Início antes de ativar notificações.';
            return;
        }

        let config;
        try {
            config = await obterConfigPush();
        } catch (erro) {
            if (status) status.textContent = erro.message;
            return;
        }

        if (!config) return;

        if (!config.enabled) {
            if (botao) botao.disabled = true;
            if (teste) teste.hidden = true;
            if (status) status.textContent = 'Notificações aguardando configuração do servidor.';
            return;
        }

        const assinatura = await assinaturaAtual();
        const ativa = Boolean(assinatura) && Notification.permission === 'granted';

        if (botao) {
            botao.disabled = false;
            botao.dataset.enabled = ativa ? 'true' : 'false';
            botao.textContent = ativa ? 'Desativar notificações' : 'Ativar notificações';
        }

        if (teste) teste.hidden = !ativa;

        if (status) {
            if (Notification.permission === 'denied') {
                status.textContent = 'Notificações bloqueadas nas configurações do navegador.';
            } else if (ativa) {
                status.textContent = 'Notificações ativadas neste dispositivo.';
            } else {
                status.textContent = 'Ative para receber avisos quando novos treinos forem enviados.';
            }
        }
    }

    async function ativarNotificacoes() {
        const config = await obterConfigPush();

        if (!config || !config.enabled || !config.public_key) {
            throw new Error('O servidor ainda não está configurado para Web Push.');
        }

        const permissao = await Notification.requestPermission();

        if (permissao !== 'granted') {
            throw new Error('A permissão de notificações não foi concedida.');
        }

        const registro = await obterRegistro();
        if (!registro) throw new Error('Service Worker indisponível.');

        let subscription = await registro.pushManager.getSubscription();

        if (!subscription) {
            subscription = await registro.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ParaUint8Array(config.public_key)
            });
        }

        await sincronizarAssinaturaComServidor(subscription);
    }

    async function desativarNotificacoes() {
        const subscription = await assinaturaAtual();
        if (!subscription) return;

        await fetch('/api/push/unsubscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ endpoint: subscription.endpoint })
        });

        await subscription.unsubscribe();
    }

    async function alternarNotificacoes() {
        const botao = document.getElementById('btnNotificacoesPwa');
        const status = document.getElementById('pwaNotificationStatus');

        if (!botao) return;

        botao.disabled = true;

        try {
            const habilitada = botao.dataset.enabled === 'true';

            if (habilitada) {
                await desativarNotificacoes();
            } else {
                await ativarNotificacoes();
            }

            await atualizarEstadoNotificacoes();

        } catch (erro) {
            console.error(erro);
            if (status) status.textContent = erro.message || 'Não foi possível alterar as notificações.';
            botao.disabled = false;
        }
    }

    async function enviarNotificacaoTeste() {
        const botao = document.getElementById('btnTesteNotificacaoPwa');
        const status = document.getElementById('pwaNotificationStatus');

        if (botao) botao.disabled = true;

        try {
            const resposta = await fetch('/api/push/teste', { method: 'POST' });
            const dados = await resposta.json().catch(() => ({}));

            if (!resposta.ok) {
                throw new Error(dados.detail || 'Não foi possível enviar a notificação de teste.');
            }

            if (status) status.textContent = 'Notificação de teste enviada.';

        } catch (erro) {
            if (status) status.textContent = erro.message;
        } finally {
            if (botao) botao.disabled = false;
        }
    }

    document.addEventListener('DOMContentLoaded', async () => {
        await registrarServiceWorker();

        const instalar = document.getElementById('btnInstalarPwa');
        const notificacoes = document.getElementById('btnNotificacoesPwa');
        const teste = document.getElementById('btnTesteNotificacaoPwa');

        if (instalar) instalar.addEventListener('click', instalarPwa);
        if (notificacoes) notificacoes.addEventListener('click', alternarNotificacoes);
        if (teste) teste.addEventListener('click', enviarNotificacaoTeste);

        atualizarEstadoInstalacao();
        await atualizarEstadoNotificacoes();
    });
})();
