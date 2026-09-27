const modalidades = ["Corrida", "Natação", "Musculação"];
const dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"];
let treinosBase = [];

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
            select.addEventListener('change', atualizar);
            preview.append(elemento('p', 'day-empty', 'Sem treino para enviar neste dia.'));
            card.append(cabecalho, label, select, preview); grade.append(card);
        }
        painel.append(grade); corpo.append(painel);
    });
    formatarDatas(); atualizarResumo();
}

function revisarPlanejamento() {
    const data = document.getElementById('dataSegunda').value;
    if (!data) { mostrarMensagem('Selecione a segunda-feira da semana.', true); return; }
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
        if (quantidade) conteudo.append(grupo);
    });
    if (!total) { mostrarMensagem('Selecione pelo menos um treino.', true); return; }
    document.getElementById('resumoRevisao').textContent = `${total} treino(s) · Semana de ${data.split('-').reverse().join('/')}`;
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

document.getElementById("dataSegunda").addEventListener("change", () => {
    const input = document.getElementById("dataSegunda");
    if (input.value) {
        const corrigida = obterSegunda(input.value);
        if (input.value !== corrigida) {
            input.value = corrigida;
            mostrarMensagem("A data foi ajustada para a segunda-feira da semana selecionada.", false);
        }
    }
    formatarDatas();
});

async function duplicarSemanaAnterior() {
    const dataSegunda = document.getElementById("dataSegunda").value;
    if (!dataSegunda) {
        mostrarMensagem("Selecione primeiro a semana de destino.", true);
        return;
    }

    const [ano, mes, dia] = dataSegunda.split("-").map(Number);
    const destino = new Date(ano, mes - 1, dia);
    const origem = new Date(destino);
    origem.setDate(origem.getDate() - 7);
    const origemTexto = `${origem.getFullYear()}-${String(origem.getMonth()+1).padStart(2,"0")}-${String(origem.getDate()).padStart(2,"0")}`;

    if (!confirm(`Duplicar os treinos da semana ${origemTexto} para ${dataSegunda}?`)) return;

    const botao = document.getElementById("btnDuplicar");
    try {
        botao.disabled = true;
        botao.textContent = "Duplicando...";
        const resposta = await fetch("/api/treinos/semana/duplicar", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({origem_segunda: origemTexto, destino_segunda: dataSegunda})
        });
        const resultado = await resposta.json().catch(() => ({}));
        if (!resposta.ok) throw new Error(resultado.detail || "Não foi possível duplicar a semana.");
        mostrarMensagem(`${resultado.mensagem} ${resultado.total_enviados} treinos enviados.`, false);
    } catch (erro) {
        mostrarMensagem(erro.message || "Erro ao duplicar semana.", true);
    } finally {
        botao.disabled = false;
        botao.textContent = "Duplicar semana anterior";
    }
}

async function enviarPlanejamento() {
    const mensagem = document.getElementById("mensagem");
    const botao = document.getElementById("btnConfirmarEnvio");
    if (botao.disabled) return;
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
    carregarTreinos();
    definirSegundaAtual();
});
