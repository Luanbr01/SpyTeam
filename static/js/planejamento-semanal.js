const modalidades = ["Corrida", "Natação", "Musculação"];
const dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"];
let treinosBase = [];
let rascunhoVersao = 0;
let semanaAtual = '';
let alteracoesPendentes = false;
let operacaoPlanejamento = false;
let enviandoPlanejamento = false;
let destinatariosRevisados = {};

async function requisicaoGestao(caminho, opcoes) {
    const resposta = await fetch('/api/gestao-professor/' + caminho, opcoes);
    if (resposta.status === 401 || resposta.status === 403) {
        window.location.href = '/login';
        throw new Error('Sua sessão expirou. Entre novamente.');
    }
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível completar a operação.');
    return dados;
}

function coletarSelecoes() {
    const itens = [];
    modalidades.forEach(modalidade => dias.forEach((_, dia) => {
        const valor = document.getElementById(`${idModalidade(modalidade)}-${dia}`)?.value;
        if (valor) itens.push({dia, treino_base_id: Number(valor)});
    }));
    return itens;
}

function marcarAlteracao() {
    alteracoesPendentes = true;
    document.getElementById('estadoRascunho').textContent = 'Há alterações não salvas. Salve o rascunho para continuar depois.';
}

function bloquearEditor(bloquear) {
    operacaoPlanejamento = bloquear;
    document.querySelectorAll('.select-treino').forEach(s => {
        const modalidade = modalidades.find(m => s.id.startsWith(idModalidade(m) + '-'));
        s.disabled = bloquear || !treinosBase.some(t => normalizarTexto(t.modalidade) === normalizarTexto(modalidade));
    });
    ['dataSegunda', 'btnSalvarRascunho', 'btnRestaurarRascunho', 'btnDuplicar', 'btnEnviar'].forEach(id => document.getElementById(id).disabled = bloquear);
    if (!bloquear) atualizarResumo();
}

function aplicarSelecoes(itens) {
    let indisponiveis = 0;
    document.querySelectorAll('.select-treino').forEach(s => { s.value = ''; });
    for (const item of itens) {
        const treino = treinosBase.find(t => t.id === item.treino_base_id);
        const select = treino && document.getElementById(`${idModalidade(treino.modalidade)}-${item.dia}`);
        if (select && [...select.options].some(o => o.value === String(item.treino_base_id))) select.value = item.treino_base_id;
        else indisponiveis++;
    }
    document.querySelectorAll('.select-treino').forEach(s => s.dispatchEvent(new Event('change')));
    return indisponiveis;
}

async function salvarRascunho() {
    if (operacaoPlanejamento || !semanaAtual) return;
    if (rascunhoVersao === null) { mostrarMensagem('Carregue o rascunho antes de salvar.', true); return; }
    bloquearEditor(true);
    try {
        const dados = await requisicaoGestao(`rascunho?data_segunda=${semanaAtual}`, {
            method: 'PUT', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({itens: coletarSelecoes(), versao: rascunhoVersao})
        });
        rascunhoVersao = dados.versao;
        alteracoesPendentes = false;
        document.getElementById('estadoRascunho').textContent = dados.mensagem;
        mostrarMensagem(dados.mensagem);
    } catch (erro) { mostrarMensagem(erro.message, true); }
    finally { bloquearEditor(false); }
}

async function restaurarRascunho(inicial = false) {
    if (operacaoPlanejamento || !semanaAtual) return;
    if (!inicial && alteracoesPendentes && !confirm('Carregar o rascunho salvo e substituir as alterações desta tela?')) return;
    bloquearEditor(true);
    try {
        const dados = await requisicaoGestao(`rascunho?data_segunda=${semanaAtual}`);
        rascunhoVersao = dados.versao;
        const faltantes = aplicarSelecoes(dados.itens);
        alteracoesPendentes = Boolean(faltantes);
        document.getElementById('estadoRascunho').textContent = faltantes
            ? `${faltantes} treino(s) do rascunho não estão mais disponíveis. Revise e salve novamente.`
            : dados.versao ? 'Rascunho carregado. Nenhum treino foi enviado.' : 'Esta semana ainda não tem rascunho salvo.';
    } catch (erro) {
        // Sem a versão do servidor não é seguro sobrescrever um rascunho.
        rascunhoVersao = null;
        document.getElementById('estadoRascunho').textContent = 'Não foi possível carregar o rascunho. Tente novamente.';
        mostrarMensagem(erro.message, true);
    } finally { bloquearEditor(false); }
}

window.addEventListener('beforeunload', event => {
    if (alteracoesPendentes) { event.preventDefault(); event.returnValue = ''; }
});


function normalizarTexto(texto) {
    return String(texto || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim();
}

function idModalidade(modalidade) {
    return normalizarTexto(modalidade).replace(/\s+/g, "-");
}

function elemento(tag, classe, texto) {
    const el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto !== undefined) el.textContent = texto;
    return el;
}

function detalhesTreino(treino) {
    const bloco = elemento('div', 'workout-preview');
    bloco.append(elemento('span', 'preview-label', 'O QUE SERÁ FEITO'), elemento('h4', '', treino.titulo), elemento('p', 'workout-description', treino.descricao || 'Descrição não informada.'));
    if (treino.ritmo_alvo) bloco.append(elemento('p', 'workout-pace', `Ritmo alvo: ${treino.ritmo_alvo}`));
    return bloco;
}

function atualizarResumo() {
    const total = document.querySelectorAll('.select-treino').length ? Array.from(document.querySelectorAll('.select-treino')).filter(s => s.value).length : 0;
    document.getElementById('resumoSelecao').textContent = total ? `${total} treino${total > 1 ? 's' : ''} selecionado${total > 1 ? 's' : ''} na semana. Confira antes de enviar.` : 'Nenhum treino selecionado nesta semana.';
    document.getElementById('btnEnviar').disabled = !total;
    modalidades.forEach(modalidade => {
        const qtd = Array.from(document.querySelectorAll(`#painel-${idModalidade(modalidade)} select`)).filter(s => s.value).length;
        document.getElementById(`contador-${idModalidade(modalidade)}`).textContent = `${qtd}/5`;
    });
}

function montarTabela() {
    const corpo = document.getElementById('corpoTabela');
    const filtros = document.getElementById('modalidadesPlanner');
    corpo.replaceChildren(); filtros.replaceChildren();
    modalidades.forEach((modalidade, index) => {
        const chave = idModalidade(modalidade);
        const botao = elemento('button', 'planner-modality');
        botao.type = 'button';
        botao.setAttribute('aria-pressed', String(index === 0));
        botao.setAttribute('aria-controls', `painel-${chave}`);
        botao.append(elemento('span', '', modalidade));
        const contador = elemento('span', 'modality-count', '0/5');
        contador.id = `contador-${chave}`; botao.append(contador);
        const painel = elemento('section', 'planner-panel');
        painel.id = `painel-${chave}`; painel.hidden = index !== 0;
        painel.setAttribute('aria-label', `Semana de ${modalidade}`);
        botao.addEventListener('click', () => {
            filtros.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === botao)));
            corpo.querySelectorAll('.planner-panel').forEach(p => p.hidden = p !== painel);
        });
        filtros.append(botao);
        const lista = treinosBase.filter(t => normalizarTexto(t.modalidade) === normalizarTexto(modalidade));
        if (!lista.length) painel.append(elemento('p', 'planner-empty', `Nenhum treino base de ${modalidade} cadastrado. Cadastre um treino na opção Criar treino.`));
        const grade = elemento('div', 'planner-days');
        for (let dia = 0; dia < 5; dia++) {
            const card = elemento('article', 'planner-day');
            const cabecalho = elemento('div', 'day-heading');
            const data = elemento('span', 'day-date'); data.dataset.dia = dia;
            cabecalho.append(elemento('h3', '', `${dias[dia]}-feira`), data);
            const select = elemento('select', 'select-treino');
            select.id = `${chave}-${dia}`;
            const label = elemento('label', '', 'Treino do dia'); label.htmlFor = select.id;
            const vazio = elemento('option', '', 'Nenhum treino'); vazio.value = ''; select.append(vazio);
            lista.forEach(t => { const option = elemento('option', '', t.titulo); option.value = t.id; select.append(option); });
            select.disabled = !lista.length;
            const preview = elemento('div', 'day-preview');
            const atualizar = () => {
                const treino = treinosBase.find(t => String(t.id) === select.value);
                preview.replaceChildren(treino ? detalhesTreino(treino) : elemento('p', 'day-empty', 'Sem treino para enviar neste dia.'));
                card.classList.toggle('has-workout', Boolean(treino));
                atualizarResumo();
            };
            select.addEventListener('change', () => { atualizar(); marcarAlteracao(); });
            preview.append(elemento('p', 'day-empty', 'Sem treino para enviar neste dia.'));
            card.append(cabecalho, label, select, preview); grade.append(card);
        }
        painel.append(grade); corpo.append(painel);
    });
    formatarDatas(); atualizarResumo();
}

async function revisarPlanejamento() {
    if (operacaoPlanejamento) return;
    const data = document.getElementById('dataSegunda').value;
    if (!data) { mostrarMensagem('Selecione a segunda-feira da semana.', true); return; }
    bloquearEditor(true);
    try {
        const contexto = await requisicaoGestao(`semana?data_segunda=${data}`);
        destinatariosRevisados = contexto.destinatarios;
    } catch (erro) { mostrarMensagem(erro.message, true); return; }
    finally { bloquearEditor(false); }
    const conteudo = document.getElementById('conteudoRevisao'); conteudo.replaceChildren();
    let total = 0;
    modalidades.forEach(modalidade => {
        const grupo = elemento('section', 'review-group');
        grupo.append(elemento('h3', '', modalidade));
        let quantidade = 0;
        dias.forEach((dia, i) => {
            const select = document.getElementById(`${idModalidade(modalidade)}-${i}`);
            const treino = treinosBase.find(t => String(t.id) === select?.value);
            if (!treino) return;
            quantidade++; total++;
            const card = elemento('article', 'review-workout');
            const dataDia = document.querySelector(`[data-dia="${i}"]`).textContent;
            card.append(elemento('h4', 'review-day', `${dia}-feira · ${dataDia}`), detalhesTreino(treino)); grupo.append(card);
        });
        if (quantidade) {
            const alunos = destinatariosRevisados[modalidade] || [];
            const detalhes = elemento('details', 'gestao-destinatarios');
            detalhes.append(elemento('summary', '', `${alunos.length} aluno(s) receberão os ${quantidade} treino(s) de ${modalidade}`));
            detalhes.append(elemento('p', '', alunos.length ? alunos.map(a => a.nome).join(' • ') : 'Não há alunos cadastrados nesta modalidade. Esses treinos não terão destinatários.'));
            grupo.prepend(detalhes);
            conteudo.append(grupo);
        }
    });
    if (!total) { mostrarMensagem('Selecione pelo menos um treino.', true); return; }
    document.getElementById('resumoRevisao').textContent = `${total} treino(s) · Semana de ${data.split('-').reverse().join('/')}`;
    const temDestinatarios = modalidades.some(m => (destinatariosRevisados[m] || []).length && coletarSelecoes().some(i => normalizarTexto(treinosBase.find(t => t.id === i.treino_base_id)?.modalidade) === normalizarTexto(m)));
    document.getElementById('btnConfirmarEnvio').disabled = !temDestinatarios;
    if (!temDestinatarios) conteudo.prepend(elemento('p', 'message error', 'Nenhum aluno receberia este planejamento. Confira as modalidades dos alunos.'));
    document.getElementById('revisaoSemana').showModal();
}

async function carregarTreinos() {
    try {
        const resposta = await fetch("/api/treinos-base");
        if (resposta.status === 401 || resposta.status === 403) {
            window.location.href = "/login";
            return;
        }
        if (!resposta.ok) throw new Error("Não foi possível carregar os treinos base.");
        treinosBase = await resposta.json();
        montarTabela();
        semanaAtual = document.getElementById('dataSegunda').value;
        await restaurarRascunho(true);
    } catch (erro) {
        console.error(erro);
        mostrarMensagem("Erro ao carregar os treinos base.", true);
    }
}

function formatarDatas() {
    const input = document.getElementById("dataSegunda");
    if (!input.value) {
        document.querySelectorAll('[data-dia]').forEach(el => el.textContent = '—');
        return;
    }

    const [ano, mes, dia] = input.value.split("-").map(Number);
    const segunda = new Date(ano, mes - 1, dia);

    for (let i = 0; i < 5; i++) {
        const data = new Date(segunda);
        data.setDate(segunda.getDate() + i);
        document.querySelectorAll(`[data-dia="${i}"]`).forEach(el => {
            el.textContent = `${String(data.getDate()).padStart(2,"0")}/${String(data.getMonth()+1).padStart(2,"0")}`;
        });
    }
}

function obterSegunda(valor) {
    const [ano, mes, dia] = valor.split("-").map(Number);
    const data = new Date(ano, mes - 1, dia);
    const diaSemana = data.getDay();
    const voltar = diaSemana === 0 ? 6 : diaSemana - 1;
    data.setDate(data.getDate() - voltar);
    return `${data.getFullYear()}-${String(data.getMonth()+1).padStart(2,"0")}-${String(data.getDate()).padStart(2,"0")}`;
}

function definirSegundaAtual() {
    const input = document.getElementById("dataSegunda");
    if (!input.value) {
        const hoje = new Date();
        input.value = obterSegunda(`${hoje.getFullYear()}-${String(hoje.getMonth()+1).padStart(2,"0")}-${String(hoje.getDate()).padStart(2,"0")}`);
    }
    formatarDatas();
}

document.getElementById('dataSegunda').addEventListener('change', async () => {
    const input = document.getElementById('dataSegunda');
    if (!input.value) { input.value = semanaAtual; return; }
    if (alteracoesPendentes && !confirm('Trocar de semana? As alterações não salvas desta tela serão descartadas.')) {
        input.value = semanaAtual; return;
    }
    input.value = obterSegunda(input.value);
    semanaAtual = input.value;
    aplicarSelecoes([]);
    alteracoesPendentes = false;
    formatarDatas();
    await restaurarRascunho(true);
});

async function duplicarSemanaAnterior() {
    if (operacaoPlanejamento || !semanaAtual) return;
    if (alteracoesPendentes && !confirm('Substituir a seleção atual pelos treinos da semana anterior?')) return;
    const [ano, mes, dia] = semanaAtual.split('-').map(Number);
    const origem = new Date(ano, mes - 1, dia - 7);
    const data = `${origem.getFullYear()}-${String(origem.getMonth()+1).padStart(2,'0')}-${String(origem.getDate()).padStart(2,'0')}`;
    bloquearEditor(true);
    try {
        const dados = await requisicaoGestao(`planejamento?data_segunda=${data}`);
        if (dados.conflitos.length) throw new Error('A semana anterior possui mais de um treino no mesmo dia e modalidade. Monte a seleção manualmente para escolher quais reutilizar.');
        if (!dados.itens.length) throw new Error('A semana anterior não tem treinos disponíveis para reutilizar.');
        const faltantes = aplicarSelecoes(dados.itens);
        marcarAlteracao();
        mostrarMensagem(`Semana anterior carregada no editor. ${faltantes ? faltantes + ' treino(s) não estão mais disponíveis. ' : ''}Confira e use Revisar e enviar para enviar aos alunos.`);
    } catch (erro) { mostrarMensagem(erro.message, true); }
    finally { bloquearEditor(false); }
}

async function enviarPlanejamento() {
    const mensagem = document.getElementById("mensagem");
    const botao = document.getElementById("btnConfirmarEnvio");
    if (botao.disabled || enviandoPlanejamento) return;
    const dataSegunda = document.getElementById("dataSegunda").value;

    mensagem.textContent = "";
    mensagem.className = "message";

    if (!dataSegunda) {
        mostrarMensagem("Selecione a segunda-feira da semana.", true);
        return;
    }

    const dados = [];
    for (let dia = 0; dia < 5; dia++) {
        modalidades.forEach(modalidade => {
            const select = document.getElementById(`${idModalidade(modalidade)}-${dia}`);
            if (select && select.value) {
                dados.push({ dia, treino_base_id: Number(select.value) });
            }
        });
    }

    if (!dados.length) {
        mostrarMensagem("Selecione pelo menos um treino.", true);
        return;
    }

    try {
        botao.disabled = true;
        botao.textContent = "Enviando...";
        enviandoPlanejamento = true;
        bloquearEditor(true);

        const resposta = await fetch(`/api/treinos/semana?data_segunda=${encodeURIComponent(dataSegunda)}`, {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify(dados)
        });

        const resultado = await resposta.json().catch(() => ({}));
        if (!resposta.ok) {
            throw new Error(resultado.detail || "Erro ao enviar planejamento.");
        }

        mostrarMensagem(`${resultado.mensagem || "Planejamento enviado com sucesso!"} ${resultado.total_enviados || 0} treinos enviados.`, false);
    } catch (erro) {
        console.error(erro);
        mostrarMensagem(erro.message || "Erro ao enviar planejamento.", true);
    } finally {
        enviandoPlanejamento = false;
        bloquearEditor(false);
        botao.disabled = false;
        botao.textContent = "Confirmar envio";
        document.getElementById('revisaoSemana').close();
        document.getElementById('mensagem').scrollIntoView({behavior: 'smooth', block: 'center'});
    }
}

function mostrarMensagem(texto, erro = false) {
    const elemento = document.getElementById("mensagem");
    elemento.textContent = texto;
    elemento.className = `message ${erro ? "error" : "success"}`;
}

document.addEventListener("DOMContentLoaded", () => {
    definirSegundaAtual();
    carregarTreinos();
});

document.getElementById('revisaoSemana').addEventListener('cancel', event => { if (enviandoPlanejamento) event.preventDefault(); });
