(() => {
    'use strict';
    const status = document.getElementById('stravaStatus');
    if (!status || !window.StravaView) return;
    const V = window.StravaView;
    const connect = document.getElementById('stravaConnect');
    const sync = document.getElementById('stravaSync');
    const disconnect = document.getElementById('stravaDisconnect');
    const badge = document.getElementById('stravaConnection');
    const list = document.getElementById('stravaActivities');
    const count = document.getElementById('stravaCount');
    const filter = document.getElementById('stravaFilter');
    const dialog = document.getElementById('stravaDetail');
    const mapElement = document.getElementById('stravaMap');
    const mapStatus = document.getElementById('stravaMapStatus');
    const resetMap = document.getElementById('stravaMapReset');
    let activities = [], busy = false, connected = false, map = null, bounds = null;
    let cooldown = 0, timer = null, autoPending = false;
    const callbackMessages = {
        connected: 'Strava conectado! Carregando suas atividades...',
        expired: 'A conexão expirou. Toque em Conectar com Strava novamente.',
        cancelled: 'Você cancelou a autorização do Strava.',
        scope: 'Autorize a leitura das atividades para concluir a conexão.',
        linked: 'Esta conta Strava já está vinculada a outro aluno.',
        error: 'Não foi possível conectar. Tente novamente.'
    };
    const current = new URL(location.href);
    const result = current.searchParams.get('strava');
    if (result) {
        current.searchParams.delete('strava');
        history.replaceState(null, '', current.pathname + current.search + current.hash);
    }
    function node(tag, text, className) {
        const el = document.createElement(tag);
        if (text !== undefined) el.textContent = text;
        if (className) el.className = className;
        return el;
    }
    async function call(path, method = 'GET') {
        const response = await fetch('/api/strava/' + path, {method, cache: 'no-store'});
        const data = await response.json();
        if (!response.ok) {
            const error = new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível consultar o Strava.');
            error.status = response.status;
            error.retryAfter = Number(response.headers.get('Retry-After') || 0);
            throw error;
        }
        return data;
    }
    function buttons() {
        connect.disabled = busy;
        disconnect.disabled = busy;
        const remaining = Math.max(0, Math.ceil((cooldown - Date.now()) / 1000));
        sync.disabled = busy || remaining > 0;
        sync.textContent = busy ? 'Aguarde...' : remaining ? `Atualizar em ${remaining}s` : 'Atualizar atividades';
    }
    function wait(seconds, auto) {
        clearTimeout(timer);
        cooldown = Date.now() + Math.max(0, seconds) * 1000;
        autoPending = auto;
        const tick = () => {
            buttons();
            if (Date.now() < cooldown) timer = setTimeout(tick, 1000);
            else if (autoPending && connected && !busy) {
                autoPending = false;
                action(syncData);
            } else if (autoPending && connected) timer = setTimeout(tick, 500);
        };
        tick();
    }
    async function action(fn) {
        if (busy) return;
        busy = true; buttons();
        try { await fn(); }
        catch (error) {
            status.textContent = error.message;
            if ([401, 403, 409].includes(error.status)) {
                if (error.status === 409) { connect.hidden = false; connect.textContent = 'Reconectar com Strava'; }
                activities = []; empty('Atualize sua conexão', 'Entre novamente ou reconecte o Strava para continuar.');
                count.textContent = '';
                if (dialog.open) dialog.close();
            }
            if (error.retryAfter > 0 && error.retryAfter <= 60) wait(error.retryAfter, activities.length === 0);
        }
        finally { busy = false; list.setAttribute('aria-busy', 'false'); buttons(); }
    }
    async function load() {
        const data = await call('status');
        connected = data.connected;
        connect.hidden = !data.enabled || connected;
        sync.hidden = !connected || !data.enabled;
        disconnect.hidden = !connected;
        badge.textContent = connected ? 'Strava conectado' : 'Strava não conectado';
        badge.classList.toggle('is-connected', connected);
        status.textContent = !data.enabled ? 'Integração aguardando configuração.' : connected ?
            'Sua conta está conectada. As atividades são visíveis somente para você.' : 'Conecte sua conta para consultar as atividades aqui.';
        if (!connected) {
            activities = []; count.textContent = '';
            empty('Suas atividades estarão aqui', 'Conecte sua conta Strava para ver pace, distância, tempo e percurso.');
        }
        return data;
    }
    function empty(title, message) {
        const el = node('div', undefined, 'strava-empty');
        el.append(node('strong', title), node('p', message));
        list.replaceChildren(el);
    }
    function metric(label, value) {
        const box = node('div');
        box.append(node('dt', label), node('dd', value));
        return box;
    }
    function render() {
        list.replaceChildren();
        const selected = activities.filter(a => filter.value === 'all' || V.group(a.sport_type) === filter.value);
        count.textContent = `${selected.length} de ${activities.length} atividade(s) carregada(s)`;
        if (!selected.length) {
            empty(activities.length ? 'Nenhuma atividade nesta modalidade' : 'Nenhuma atividade disponível',
                activities.length ? 'Escolha outra modalidade ou a opção Todas.' : 'Confira se há atividades públicas ou para seguidores na conta conectada.');
            return;
        }
        for (const item of selected) {
            const card = node('article', undefined, 'strava-activity');
            const head = node('div', undefined, 'strava-card-head');
            const hasMap = V.decodePolyline(item.summary_polyline).length > 1;
            head.append(node('span', V.sportName(item.sport_type), 'strava-sport'),
                node('span', hasMap ? 'Percurso disponível' : 'Sem percurso', 'strava-route-badge'));
            const rhythm = V.rhythm(item);
            const metrics = node('dl', undefined, 'strava-metrics');
            metrics.append(metric('Distância', V.distance(item)), metric(rhythm.label, rhythm.value),
                metric('Em movimento', V.duration(item.moving_time)));
            const open = node('button', 'Ver detalhes' + (hasMap ? ' e mapa' : ''), 'strava-open');
            open.type = 'button';
            open.setAttribute('aria-label', `Ver detalhes de ${item.name}`);
            open.addEventListener('click', () => showDetail(item));
            card.append(head, node('h3', item.name), node('p', V.date(item), 'strava-activity-date'), metrics, open);
            list.append(card);
        }
    }
    function removeMap() {
        if (map) { map.remove(); map = null; }
        bounds = null;
        resetMap.hidden = true;
        mapElement.hidden = true;
    }
    function showDetail(item) {
        removeMap();
        document.getElementById('stravaDetailSport').textContent = V.sportName(item.sport_type);
        document.getElementById('stravaDetailTitle').textContent = item.name;
        document.getElementById('stravaDetailDate').textContent = V.date(item);
        const rhythm = V.rhythm(item);
        const gain = V.number(item.total_elevation_gain);
        const speed = V.number(item.average_speed);
        const metrics = document.getElementById('stravaDetailMetrics');
        metrics.replaceChildren(metric('Distância', V.distance(item)), metric(rhythm.label, rhythm.value),
            metric('Tempo em movimento', V.duration(item.moving_time)), metric('Tempo total (com pausas)', V.duration(item.elapsed_time)),
            metric('Ganho de elevação', gain === null ? '—' : `${V.numeric(gain, 0)} m`));
        if (rhythm.label !== 'Velocidade média' && speed !== null && speed > 0)
            metrics.append(metric('Velocidade média', `${V.numeric(speed * 3.6, 1)} km/h`));
        document.getElementById('stravaPaceNote').textContent = rhythm.note;
        document.getElementById('stravaOriginal').href = 'https://www.strava.com/activities/' + encodeURIComponent(item.id);
        mapStatus.textContent = '';
        dialog.showModal();
        const points = V.decodePolyline(item.summary_polyline);
        if (!points.length) {
            mapStatus.textContent = 'Mapa indisponível para esta atividade. Ela pode ter sido registrada sem GPS ou o percurso não foi disponibilizado pelo Strava.';
            return;
        }
        if (!window.L) {
            mapStatus.textContent = 'Não foi possível carregar o mapa. Recarregue a página e tente novamente.';
            return;
        }
        mapElement.hidden = false;
        resetMap.hidden = false;
        mapStatus.textContent = 'Verde: início · Azul: chegada. Arraste o mapa ou use os controles de zoom.';
        try {
            map = L.map(mapElement, {scrollWheelZoom: false});
            L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
                referrerPolicy: 'strict-origin-when-cross-origin'
            }).on('tileerror', () => {
                mapStatus.textContent = 'O mapa de fundo não carregou. O traçado permanece visível; confira sua conexão com a internet.';
            }).addTo(map);
            const route = L.polyline(points, {color: '#FC4C02', weight: 4, opacity: .95}).addTo(map);
            L.circleMarker(points[0], {radius: 6, color: '#fff', weight: 2, fillColor: '#199660', fillOpacity: 1}).addTo(map).bindTooltip('Início');
            L.circleMarker(points[points.length - 1], {radius: 6, color: '#fff', weight: 2, fillColor: '#245bc0', fillOpacity: 1}).addTo(map).bindTooltip('Chegada');
            bounds = route.getBounds();
            map.fitBounds(bounds, {padding: [24, 24], maxZoom: 16});
            requestAnimationFrame(() => { if (map) map.invalidateSize(); });
        } catch (_) {
            removeMap();
            mapStatus.textContent = 'Não foi possível exibir este percurso. Os demais dados da atividade continuam disponíveis.';
        }
    }
    async function syncData() {
        list.setAttribute('aria-busy', 'true');
        status.textContent = 'Consultando atividades no Strava...';
        const data = await call('sync', 'POST');
        activities = data.activities;
        render();
        status.textContent = `Atualizado às ${new Date(data.synced_at * 1000).toLocaleTimeString('pt-BR')}.`;
        wait(30, false);
    }
    async function initial() {
        const data = await load();
        if (callbackMessages[result]) status.textContent = callbackMessages[result];
        if (data.connected && data.enabled) {
            if (data.next_sync_in > 0) {
                empty('Preparando suas atividades', 'Uma consulta foi feita há pouco. As atividades serão carregadas assim que o intervalo de atualização terminar.');
                wait(data.next_sync_in, true);
            } else await syncData();
        }
    }
    connect.addEventListener('click', () => action(async () => {
        status.textContent = 'Abrindo o Strava para autorizar a conexão...';
        const data = await call('connect', 'POST');
        window.location.assign(data.url);
    }));
    sync.addEventListener('click', () => action(syncData));
    disconnect.addEventListener('click', () => {
        if (!window.confirm('Desconectar sua conta Strava do SpyTeam?')) return;
        action(async () => {
            const data = await call('disconnect', 'POST');
            clearTimeout(timer); autoPending = false; cooldown = 0;
            if (dialog.open) dialog.close();
            await load();
            status.textContent = data.message;
        });
    });
    filter.addEventListener('change', render);
    document.getElementById('stravaDetailClose').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', removeMap);
    dialog.addEventListener('click', event => {
        const r = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)) dialog.close();
    });
    resetMap.addEventListener('click', () => { if (map && bounds) map.fitBounds(bounds, {padding: [24, 24], maxZoom: 16}); });
    window.addEventListener('pagehide', () => {
        clearTimeout(timer); autoPending = false;
        if (dialog.open) dialog.close();
        removeMap(); activities = []; list.replaceChildren();
    });
    window.addEventListener('pageshow', event => { if (event.persisted) action(initial); });
    action(initial);
})();
