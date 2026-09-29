(() => {
    'use strict';
    const professor = document.body.dataset.provasMode === 'professor';
    const month = document.getElementById('mesCalendario');
    if (!month) return;
    const grid = document.getElementById('calendarioGrid');
    const calendarMessage = document.getElementById('calendarioMensagem');
    const message = document.getElementById('provasMensagem');
    const dayDialog = document.getElementById('provaDiaDialog');
    const formDialog = document.getElementById('provaFormDialog');
    const filter = document.getElementById('provasFiltro');
    const presets = {
        'Corrida': ['5 km', '7 km', '10 km', '15 km', '21 km', '42 km'],
        'Natação': ['50 m', '100 m', '200 m', '400 m', '800 m', '1.500 m'],
        'Musculação': ['Livre']
    };
    let races = [], workouts = [], upcoming = [], editing = null, selectedDay = '', selected = new Set(), choices = [];
    let sequence = 0, saving = false;
    const localDate = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    const dateBr = value => String(value).split('-').reverse().join('/');
    const icon = modality => modality === 'Corrida' ? '🏃' : modality === 'Natação' ? '🏊' : '🏋️';
    function el(tag, text, cls) {
        const n = document.createElement(tag);
        if (text !== undefined) n.textContent = text;
        if (cls) n.className = cls;
        return n;
    }
    function safeLink(value) {
        try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password ? u.href : null; }
        catch (_) { return null; }
    }
    async function api(path, method = 'GET', data) {
        const response = await fetch(path, {method, cache:'no-store', ...(data ? {headers:{'Content-Type':'application/json'},body:JSON.stringify(data)} : {})});
        const body = await response.json();
        if (!response.ok) {
            const detail = Array.isArray(body.detail) ? body.detail.map(e => e.msg).join(' ') : body.detail;
            throw new Error(detail || 'Não foi possível concluir. Tente novamente.');
        }
        return body;
    }
    function selectedModality(row) { return !filter || !filter.value || row.modalidade === filter.value; }
    function raceCard(row) {
        const card = el('article', undefined, 'provas-card');
        const top = el('div', undefined, 'provas-card-top');
        top.append(el('span', row.modalidade, 'provas-badge'), el('time', dateBr(row.data), 'provas-date'));
        top.querySelector('time').dateTime = row.data;
        card.append(top, el('h3', row.nome));
        const options = el('div', undefined, 'provas-tags');
        for (const option of row.opcoes) options.append(el('span', option));
        card.append(options);
        const actions = el('div', undefined, 'provas-card-actions');
        const link = safeLink(row.link_inscricao);
        if (link) {
            const a = el('a', 'Inscrição ↗', 'btn btn-primary');
            a.href = link; a.target = '_blank'; a.rel = 'noopener noreferrer';
            a.setAttribute('aria-label', `Abrir inscrição de ${row.nome} em outra aba`);
            actions.append(a);
        } else actions.append(el('span', 'Link de inscrição ainda não informado.', 'provas-hint'));
        if (professor) {
            const edit = el('button', 'Editar', 'btn btn-secondary'); edit.type = 'button';
            edit.addEventListener('click', () => openForm(row));
            const remove = el('button', 'Excluir', 'provas-delete'); remove.type = 'button';
            remove.addEventListener('click', async () => {
                if (!confirm(`Excluir a prova “${row.nome}”? Ela deixará de aparecer para os alunos.`)) return;
                remove.disabled = true;
                try {
                    await api(`/api/provas/${row.id}`, 'DELETE');
                    dayDialog.close(); message.textContent = 'Prova excluída.';
                    await loadCalendar();
                } catch (error) {
                    let note = card.querySelector('.provas-error');
                    if (!note) { note = el('p', '', 'provas-error'); note.setAttribute('role','alert'); card.append(note); }
                    note.textContent = error.message;
                } finally { remove.disabled = false; }
            });
            actions.append(edit, remove);
        }
        card.append(actions);
        return card;
    }
    function renderUpcoming() {
        const list = document.getElementById('provasLista');
        if (!list) return;
        list.replaceChildren();
        const rows = upcoming.filter(selectedModality);
        if (!rows.length) list.append(el('p', 'Nenhuma próxima prova cadastrada para esta seleção. Confira também outros meses no calendário.', 'provas-empty'));
        rows.forEach(row => list.append(raceCard(row)));
    }
    async function loadUpcoming() {
        if (professor) return;
        try {
            const data = await api('/api/provas');
            upcoming = data.provas; renderUpcoming();
            message.textContent = data.total > upcoming.length ? `Mostrando as próximas ${upcoming.length} provas. Consulte outras datas no calendário.` : '';
        } catch (error) { message.textContent = error.message; document.getElementById('provasLista').replaceChildren(); }
    }
    async function loadCalendar() {
        const version = ++sequence;
        if (!/^\d{4}-\d{2}$/.test(month.value) || !month.checkValidity()) {
            grid.replaceChildren(); calendarMessage.textContent = 'Selecione um mês entre 2000 e 2100.'; return;
        }
        const [year, m] = month.value.split('-').map(Number);
        grid.replaceChildren(); calendarMessage.textContent = 'Carregando calendário...';
        try {
            const tasks = [api(`/api/provas?ano=${year}&mes=${m}`)];
            if (professor) tasks.push(api(`/api/calendario?ano=${year}&mes=${m}`));
            const [r, w] = await Promise.all(tasks);
            if (version !== sequence) return;
            races = r.provas; workouts = w?.treinos || [];
            renderCalendar();
            calendarMessage.textContent = r.total > races.length ? `Mostrando ${races.length} provas neste mês.` : '';
        } catch (error) { if (version === sequence) calendarMessage.textContent = error.message; }
    }
    function renderCalendar() {
        grid.replaceChildren();
        const [year, m] = month.value.split('-').map(Number);
        const offset = (new Date(year, m-1, 1).getDay()+6)%7;
        const last = new Date(year, m, 0).getDate();
        for (let i=0; i<offset; i++) {
            const blank = el('div', '', 'calendar-day calendar-day-empty'); blank.setAttribute('aria-hidden','true'); grid.append(blank);
        }
        for (let d=1; d<=last; d++) {
            const date = `${month.value}-${String(d).padStart(2,'0')}`;
            const rs = races.filter(r => r.data === date && selectedModality(r));
            const ws = workouts.filter(t => t.data_planejada === date);
            const button = el('button', undefined, 'calendar-day' + (date === localDate() ? ' calendar-day-today' : ''));
            button.type = 'button';
            button.setAttribute('aria-label', `${dateBr(date)}: ${rs.length} prova(s)${professor ? ` e ${ws.length} treino(s)` : ''}`);
            if (date === localDate()) button.setAttribute('aria-current','date');
            button.append(el('span', String(d), 'calendar-day-number'));
            const counts = el('span', undefined, 'provas-day-counts');
            if (rs.length) counts.append(el('span', `P ${rs.length}`, 'provas-count-race'));
            if (ws.length) counts.append(el('span', `T ${ws.length}`, 'provas-count-workout'));
            button.append(counts);
            const names = el('span', undefined, 'calendar-day-content provas-day-names');
            rs.slice(0,2).forEach(r => names.append(el('span', r.nome, 'calendar-event prova')));
            ws.slice(0,2).forEach(t => names.append(el('span', t.titulo, `calendar-event ${t.concluido ? 'done' : 'pending'}`)));
            if (rs.length>2 || ws.length>2) names.append(el('span', 'Ver todos', 'calendar-more'));
            button.append(names);
            button.addEventListener('click', () => openDay(date, rs, ws)); grid.append(button);
        }
    }
    function openDay(date, rs, ws) {
        selectedDay = date;
        document.getElementById('provaDiaTitulo').textContent = `Agenda de ${dateBr(date)}`;
        const list = document.getElementById('provaDiaLista'); list.replaceChildren();
        if (!rs.length && !ws.length) list.append(el('p', 'Nenhum evento neste dia.', 'provas-empty'));
        if (rs.length) { list.append(el('h3', 'Provas')); rs.forEach(row => list.append(raceCard(row))); }
        if (ws.length) {
            list.append(el('h3', 'Treinos dos alunos'));
            ws.forEach(t => {
                const item = el('article', undefined, 'provas-workout');
                item.append(el('strong', t.titulo), el('p', `${t.aluno} · ${t.modalidade}`),
                    el('span', t.concluido ? 'Concluído' : 'Pendente', t.concluido ? 'provas-done' : 'provas-pending'));
                list.append(item);
            });
        }
        dayDialog.showModal();
    }
    function renderChoices() {
        const box = document.getElementById('provaOpcoes'); box.replaceChildren();
        for (const choice of choices) {
            const b = el('button', choice, 'provas-choice'); b.type = 'button'; b.setAttribute('aria-pressed', String(selected.has(choice)));
            b.addEventListener('click', () => {
                if (selected.has(choice)) selected.delete(choice); else if (selected.size < 12) selected.add(choice);
                else { document.getElementById('provaFormMensagem').textContent = 'Selecione no máximo 12 opções.'; return; }
                renderChoices();
            });
            box.append(b);
        }
    }
    function addCustom() {
        const input = document.getElementById('provaOutra');
        let value = input.value.trim().replace(/\s+/g,' ');
        if (!value) return true;
        const existing = choices.find(v => v.toLocaleLowerCase() === value.toLocaleLowerCase());
        if (existing) value = existing;
        if (selected.size >= 12 && !selected.has(value)) { document.getElementById('provaFormMensagem').textContent = 'Selecione no máximo 12 opções.'; return false; }
        if (!choices.includes(value)) choices.push(value);
        selected.add(value); input.value = ''; renderChoices(); return true;
    }
    function openForm(row = null, date = '') {
        if (dayDialog.open) dayDialog.close();
        editing = row?.id || null;
        document.getElementById('provaForm').reset();
        document.getElementById('provaFormTitulo').textContent = editing ? 'Editar prova' : 'Adicionar prova';
        document.getElementById('provaNome').value = row?.nome || '';
        document.getElementById('provaData').value = row?.data || date || localDate();
        document.getElementById('provaModalidade').value = row?.modalidade || '';
        document.getElementById('provaLink').value = row?.link_inscricao || '';
        choices = [...(presets[row?.modalidade] || [])]; selected = new Set(row?.opcoes || []);
        selected.forEach(v => { if (!choices.includes(v)) choices.push(v); });
        document.getElementById('provaOpcoesGrupo').hidden = !row?.modalidade;
        document.getElementById('provaFormMensagem').textContent = '';
        renderChoices(); formDialog.showModal();
    }
    if (professor) {
        document.getElementById('novaProva').addEventListener('click', () => openForm());
        document.getElementById('provaNesteDia').addEventListener('click', () => openForm(null, selectedDay));
        document.getElementById('provaModalidade').addEventListener('change', event => {
            selected = new Set(); choices = [...(presets[event.target.value] || [])];
            document.getElementById('provaOutra').value = '';
            document.getElementById('provaOpcoesGrupo').hidden = !event.target.value;
            document.getElementById('provaFormMensagem').textContent = ''; renderChoices();
        });
        document.getElementById('adicionarOpcao').addEventListener('click', addCustom);
        document.getElementById('provaOutra').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); addCustom(); } });
        formDialog.addEventListener('cancel', e => { if (saving) e.preventDefault(); });
        document.getElementById('provaForm').addEventListener('submit', async event => {
            event.preventDefault(); if (saving || !addCustom()) return;
            const note = document.getElementById('provaFormMensagem'); note.textContent = '';
            if (!selected.size) { note.textContent = 'Selecione pelo menos uma distância ou categoria.'; return; }
            const payload = {nome:document.getElementById('provaNome').value.trim(), data:document.getElementById('provaData').value,
                modalidade:document.getElementById('provaModalidade').value, opcoes:[...selected], link_inscricao:document.getElementById('provaLink').value.trim() || null};
            saving = true; const buttons = [...formDialog.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true);
            try {
                const saved = await api('/api/provas' + (editing ? `/${editing}` : ''), editing ? 'PUT' : 'POST', payload);
                formDialog.close(); month.value = saved.data.slice(0,7);
                message.textContent = editing ? 'Prova atualizada.' : 'Prova cadastrada e disponível para os alunos.';
                await loadCalendar();
            } catch (error) { note.textContent = error.message; }
            finally { saving = false; buttons.forEach(b => b.disabled = false); }
        });
    }
    document.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => document.getElementById(b.dataset.close).close()));
    function changeMonth(delta) {
        const [y,m] = (month.value || localDate().slice(0,7)).split('-').map(Number);
        const date = new Date(y,m-1+delta,1);
        if (date.getFullYear()<2000 || date.getFullYear()>2100) return;
        month.value = localDate(date).slice(0,7); loadCalendar();
    }
    document.getElementById('mesAnterior').addEventListener('click', () => changeMonth(-1));
    document.getElementById('mesSeguinte').addEventListener('click', () => changeMonth(1));
    month.addEventListener('change', loadCalendar);
    if (filter) filter.addEventListener('change', () => { renderUpcoming(); if (grid.children.length) renderCalendar(); });
    month.value = localDate().slice(0,7);
    loadCalendar(); loadUpcoming();
})();
