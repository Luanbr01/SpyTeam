(() => {
    'use strict';
    const status = document.getElementById('stravaStatus');
    if (!status) return;
    const connect = document.getElementById('stravaConnect');
    const sync = document.getElementById('stravaSync');
    const disconnect = document.getElementById('stravaDisconnect');
    const list = document.getElementById('stravaActivities');
    const buttons = [connect, sync, disconnect];
    let busy = false;
    const callbackMessages = {
        connected: 'Strava conectado! Toque em Atualizar atividades para consultar.',
        expired: 'A conexão expirou. Toque em Conectar com Strava novamente.',
        cancelled: 'Você cancelou a autorização do Strava.',
        scope: 'Autorize a leitura das atividades para concluir a conexão.',
        linked: 'Esta conta Strava já está vinculada a outro aluno.',
        error: 'Não foi possível conectar. Confira a configuração e tente novamente.'
    };
    const current = new URL(location.href);
    const result = current.searchParams.get('strava');
    if (result) {
        current.searchParams.delete('strava');
        history.replaceState(null, '', current.pathname + current.search + current.hash);
    }
    async function call(path, method = 'GET') {
        const response = await fetch('/api/strava/' + path, {method, cache: 'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível consultar o Strava.');
        return data;
    }
    async function load() {
        const data = await call('status');
        connect.hidden = !data.enabled;
        connect.textContent = data.connected ? 'Reconectar com Strava' : 'Conectar com Strava';
        sync.hidden = !data.connected || !data.enabled;
        disconnect.hidden = !data.connected;
        status.textContent = !data.enabled ? 'Integração aguardando configuração.' :
            data.connected ? 'Strava conectado. Atualize para consultar suas atividades.' : 'Conecte sua conta para consultar suas atividades.';
    }
    async function action(fn) {
        if (busy) return;
        busy = true;
        buttons.forEach(b => b.disabled = true);
        try { await fn(); } catch (error) { status.textContent = error.message; }
        finally { busy = false; buttons.forEach(b => b.disabled = false); }
    }
    function node(tag, text) {
        const el = document.createElement(tag);
        el.textContent = text;
        return el;
    }
    const sports = {Run: 'Corrida', TrailRun: 'Corrida em trilha', Swim: 'Natação', Ride: 'Ciclismo',
        Walk: 'Caminhada', WeightTraining: 'Musculação', Workout: 'Treino', VirtualRun: 'Corrida virtual'};
    connect.addEventListener('click', () => action(async () => {
        status.textContent = 'Abrindo o Strava...';
        const data = await call('connect', 'POST');
        window.location.assign(data.url);
    }));
    sync.addEventListener('click', () => action(async () => {
        list.replaceChildren();
        status.textContent = 'Consultando atividades...';
        const data = await call('sync', 'POST');
        for (const item of data.activities) {
            const card = document.createElement('article');
            card.className = 'strava-activity';
            const date = item.start_date ? new Date(item.start_date).toLocaleString('pt-BR') : 'Data indisponível';
            const km = (Number(item.distance || 0) / 1000).toLocaleString('pt-BR', {maximumFractionDigits: 2});
            const seconds = Math.max(0, Number(item.moving_time || 0));
            const duration = `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
            const link = node('a', 'Ver no Strava');
            link.href = 'https://www.strava.com/activities/' + encodeURIComponent(item.id);
            link.target = '_blank'; link.rel = 'noopener noreferrer';
            card.append(node('h3', item.name), node('p', `${sports[item.sport_type] || item.sport_type} · ${date}`),
                node('p', `${km} km · ${duration}`), link);
            list.append(card);
        }
        status.textContent = data.activities.length ? `${data.activities.length} atividade(s). Atualizado às ${new Date(data.synced_at * 1000).toLocaleTimeString('pt-BR')}.` :
            'Nenhuma atividade disponível com a permissão concedida.';
    }));
    disconnect.addEventListener('click', () => {
        if (!window.confirm('Desconectar sua conta Strava do SpyTeam?')) return;
        action(async () => {
            const data = await call('disconnect', 'POST');
            list.replaceChildren();
            await load();
            status.textContent = data.message;
        });
    });
    window.addEventListener('pagehide', () => list.replaceChildren());
    window.addEventListener('pageshow', event => { if (event.persisted) load().catch(e => status.textContent = e.message); });
    action(async () => { await load(); if (callbackMessages[result]) status.textContent = callbackMessages[result]; });
})();
