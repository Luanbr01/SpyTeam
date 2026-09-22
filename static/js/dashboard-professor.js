// ============================================================
// DASHBOARD-PROFESSOR.JS
// Indicadores e gráficos do painel do professor
// ============================================================

function escapeDashboard(texto) {
    return String(texto ?? '').replace(
        /[&<>'"]/g,
        caractere => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[caractere])
    );
}

function formatarPercentual(valor) {
    const numero = Number(valor || 0);
    return `${numero.toLocaleString('pt-BR', {
        minimumFractionDigits: numero % 1 ? 1 : 0,
        maximumFractionDigits: 1
    })}%`;
}

function formatarNumero(valor) {
    return Number(valor || 0).toLocaleString('pt-BR');
}

function tempoRelativo(timestamp) {
    if (!timestamp) return 'sem data';

    const segundos = Math.max(0, Math.floor(Date.now() / 1000 - Number(timestamp)));
    if (segundos < 60) return 'agora';

    const minutos = Math.floor(segundos / 60);
    if (minutos < 60) return `há ${minutos} min`;

    const horas = Math.floor(minutos / 60);
    if (horas < 24) return `há ${horas} h`;

    const dias = Math.floor(horas / 24);
    if (dias === 1) return 'há 1 dia';
    if (dias < 30) return `há ${dias} dias`;

    return new Intl.DateTimeFormat('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    }).format(new Date(Number(timestamp) * 1000));
}

function iconeAtividade(item) {
    if (item.tipo === 'treino_concluido') return '✓';

    const acao = String(item.acao || '');
    if (acao.includes('aluno')) return '👤';
    if (acao.includes('treino')) return '🏃';
    if (acao.includes('planejamento')) return '📅';
    return '•';
}

function renderizarFrequencia(dados) {
    const container = document.getElementById('frequenciaChart');
    if (!container) return;

    const pontos = Array.isArray(dados) ? dados : [];

    if (!pontos.length) {
        container.innerHTML = '<p class="dashboard-empty">Sem dados de frequência no período.</p>';
        return;
    }

    const largura = 720;
    const altura = 250;
    const margemX = 46;
    const margemTopo = 26;
    const margemBaixo = 42;
    const larguraGrafico = largura - (margemX * 2);
    const alturaGrafico = altura - margemTopo - margemBaixo;
    const maximo = Math.max(1, ...pontos.map(p => Number(p.concluidos || 0)));

    const coords = pontos.map((ponto, indice) => {
        const x = pontos.length === 1
            ? largura / 2
            : margemX + (indice * larguraGrafico / (pontos.length - 1));
        const y = margemTopo + alturaGrafico - ((Number(ponto.concluidos || 0) / maximo) * alturaGrafico);
        return { x, y, ponto };
    });

    const linhas = [0, .25, .5, .75, 1].map(fracao => {
        const y = margemTopo + alturaGrafico - (fracao * alturaGrafico);
        const valor = Math.round(maximo * fracao);
        return `
            <line x1="${margemX}" y1="${y}" x2="${largura - margemX}" y2="${y}" class="chart-grid-line" />
            <text x="${margemX - 12}" y="${y + 4}" text-anchor="end" class="chart-axis-label">${valor}</text>
        `;
    }).join('');

    const polyline = coords.map(c => `${c.x},${c.y}`).join(' ');
    const area = [
        `${coords[0].x},${margemTopo + alturaGrafico}`,
        ...coords.map(c => `${c.x},${c.y}`),
        `${coords[coords.length - 1].x},${margemTopo + alturaGrafico}`
    ].join(' ');

    const marcadores = coords.map(({x, y, ponto}) => `
        <circle cx="${x}" cy="${y}" r="6" class="chart-point" />
        <text x="${x}" y="${Math.max(16, y - 13)}" text-anchor="middle" class="chart-value">${formatarNumero(ponto.concluidos)}</text>
        <text x="${x}" y="${altura - 14}" text-anchor="middle" class="chart-x-label">${escapeDashboard(ponto.rotulo)}</text>
    `).join('');

    container.innerHTML = `
        <svg class="frequency-svg" viewBox="0 0 ${largura} ${altura}" role="img" aria-label="Treinos concluídos por semana">
            <defs>
                <linearGradient id="frequencyArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#3161CA" stop-opacity="0.24" />
                    <stop offset="100%" stop-color="#57C0FF" stop-opacity="0.02" />
                </linearGradient>
            </defs>
            ${linhas}
            <polygon points="${area}" fill="url(#frequencyArea)" />
            <polyline points="${polyline}" class="chart-line" />
            ${marcadores}
        </svg>
    `;
}

function renderizarModalidades(modalidades) {
    const lista = document.getElementById('modalidadeResumo');
    const donut = document.getElementById('modalidadeDonut');
    const totalEl = document.getElementById('modalidadeTotal');

    if (!lista || !donut || !totalEl) return;

    const itens = Array.isArray(modalidades) ? modalidades : [];
    const total = itens.reduce((soma, item) => soma + Number(item.treinos || 0), 0);
    totalEl.textContent = formatarNumero(total);

    const mapa = {
        'Corrida': {emoji: '🏃', classe: 'mod-run', cor: '#1769E0'},
        'Natação': {emoji: '🏊', classe: 'mod-swim', cor: '#32B5E8'},
        'Musculação': {emoji: '🏋️', classe: 'mod-strength', cor: '#F4A629'}
    };

    let acumulado = 0;
    const segmentos = [];

    itens.forEach(item => {
        const config = mapa[item.nome] || {emoji: '•', classe: '', cor: '#98A2B3'};
        const inicio = acumulado;
        acumulado += Number(item.percentual || 0);
        segmentos.push(`${config.cor} ${inicio}% ${acumulado}%`);
    });

    if (!total) {
        donut.style.background = '#EEF3F9';
    } else {
        donut.style.background = `conic-gradient(${segmentos.join(', ')})`;
    }

    lista.innerHTML = itens.map(item => {
        const config = mapa[item.nome] || {emoji: '•', classe: ''};
        return `
            <div class="modality-summary-item">
                <span class="modality-summary-icon ${config.classe}">${config.emoji}</span>
                <div class="modality-summary-main">
                    <strong>${escapeDashboard(item.nome)}</strong>
                    <small>${formatarNumero(item.alunos)} aluno${Number(item.alunos) === 1 ? '' : 's'}</small>
                </div>
                <div class="modality-summary-values">
                    <strong>${formatarNumero(item.treinos)}</strong>
                    <span>${formatarPercentual(item.percentual)}</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderizarAtividades(atividades) {
    const container = document.getElementById('atividadeRecente');
    if (!container) return;

    if (!Array.isArray(atividades) || !atividades.length) {
        container.innerHTML = '<p class="dashboard-empty">Ainda não há atividades registradas.</p>';
        return;
    }

    container.innerHTML = atividades.map(item => `
        <div class="activity-item">
            <span class="activity-icon ${item.tipo === 'treino_concluido' ? 'activity-success' : ''}">${iconeAtividade(item)}</span>
            <div class="activity-copy">
                <strong>${escapeDashboard(item.descricao)}</strong>
                <small>${tempoRelativo(item.timestamp)}</small>
            </div>
        </div>
    `).join('');
}

function renderizarAtencao(alunos) {
    const container = document.getElementById('alunosAtencao');
    if (!container) return;

    if (!Array.isArray(alunos) || !alunos.length) {
        container.innerHTML = `
            <div class="attention-success">
                <span>✓</span>
                <div><strong>Equipe em dia</strong><small>Nenhum aluno está inativo no momento.</small></div>
            </div>
        `;
        return;
    }

    container.innerHTML = alunos.map(aluno => {
        const inicial = escapeDashboard(String(aluno.nome || 'A').charAt(0).toUpperCase());
        const dias = aluno.dias_sem_atividade;
        const textoDias = dias === null || dias === undefined
            ? 'Sem atividade registrada'
            : `${dias} dia${dias === 1 ? '' : 's'} sem atividade`;
        const modalidades = Array.isArray(aluno.modalidades) && aluno.modalidades.length
            ? aluno.modalidades.join(' • ')
            : 'Modalidade não informada';

        return `
            <a class="attention-item" href="/alunos">
                <span class="attention-avatar">${inicial}</span>
                <div class="attention-copy">
                    <strong>${escapeDashboard(aluno.nome)}</strong>
                    <small>${escapeDashboard(modalidades)}</small>
                </div>
                <span class="attention-days">${escapeDashboard(textoDias)}</span>
            </a>
        `;
    }).join('');
}

function renderizarAvaliacoes(avaliacoes) {
    const media = document.getElementById('avaliacaoMedia');
    const estrelas = document.getElementById('avaliacaoEstrelas');
    const total = document.getElementById('avaliacaoTotal');
    const distribuicao = document.getElementById('avaliacaoDistribuicao');

    if (!media || !estrelas || !total || !distribuicao) return;

    const dados = avaliacoes || {};
    const valor = Number(dados.media || 0);
    const totalAvaliacoes = Number(dados.total || 0);

    media.textContent = totalAvaliacoes ? valor.toLocaleString('pt-BR', {minimumFractionDigits: 1, maximumFractionDigits: 1}) : '—';
    const cheias = Math.max(0, Math.min(5, Math.round(valor)));
    estrelas.textContent = totalAvaliacoes ? `${'★'.repeat(cheias)}${'☆'.repeat(5 - cheias)}` : '☆☆☆☆☆';
    total.textContent = totalAvaliacoes
        ? `${formatarNumero(totalAvaliacoes)} avaliação${totalAvaliacoes === 1 ? '' : 'ões'}`
        : 'Nenhuma avaliação no período';

    const dist = dados.distribuicao || {};
    distribuicao.innerHTML = [5,4,3,2,1].map(nota => {
        const item = dist[String(nota)] || {quantidade: 0, percentual: 0};
        return `
            <div class="rating-row">
                <span>${nota} estrela${nota === 1 ? '' : 's'}</span>
                <div class="rating-bar"><i style="width:${Math.max(0, Math.min(100, Number(item.percentual || 0)))}%"></i></div>
                <strong>${formatarPercentual(item.percentual)}</strong>
            </div>
        `;
    }).join('');
}

function preencherResumo(dados) {
    const resumo = dados.resumo || {};
    const totalAlunos = Number(resumo.total_alunos || 0);

    document.getElementById('kpiAtivos').textContent = formatarNumero(resumo.alunos_ativos);
    document.getElementById('kpiAtivosLegenda').textContent = `${formatarNumero(resumo.alunos_ativos)} de ${formatarNumero(totalAlunos)} alunos com atividade recente`;
    document.getElementById('kpiConclusao').textContent = formatarPercentual(resumo.taxa_conclusao);
    document.getElementById('kpiAderencia').textContent = formatarPercentual(resumo.aderencia_30_dias);
    document.getElementById('kpiInativos').textContent = formatarNumero(resumo.alunos_inativos);
}

async function carregarDashboardProfessor() {
    const periodo = document.getElementById('dashboardPeriodo');
    const semanas = Number(periodo?.value || 4);

    document.body.classList.add('dashboard-carregando');

    try {
        const resposta = await fetch(`/api/dashboard/professor?semanas=${semanas}`);

        if (resposta.status === 401 || resposta.status === 403) {
            window.location.href = '/login';
            return;
        }

        if (!resposta.ok) {
            throw new Error('Não foi possível carregar o dashboard.');
        }

        const dados = await resposta.json();

        preencherResumo(dados);
        renderizarFrequencia(dados.frequencia_semanal);
        renderizarModalidades(dados.modalidades);
        renderizarAtividades(dados.atividade_recente);
        renderizarAtencao(dados.alunos_atencao);
        renderizarAvaliacoes(dados.avaliacoes);
    } catch (erro) {
        console.error(erro);

        const containers = [
            'frequenciaChart',
            'modalidadeResumo',
            'atividadeRecente',
            'alunosAtencao',
            'avaliacaoDistribuicao'
        ];

        containers.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<p class="dashboard-empty">Não foi possível carregar os dados agora.</p>';
        });
    } finally {
        document.body.classList.remove('dashboard-carregando');
    }
}

async function sair(event) {
    if (event) event.preventDefault();
    await fetch('/api/logout', {method: 'POST'});
    window.location.href = '/login';
}

document.getElementById('dashboardPeriodo')?.addEventListener('change', carregarDashboardProfessor);
carregarDashboardProfessor();
