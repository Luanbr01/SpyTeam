let treinos = [];
let treinoSelecionado = null;
let notaSelecionada = 0;


// ==========================================================
// PROTEGER HTML
// ==========================================================

function escapeHtml(text) {
    return String(text ?? '').replace(
        /[&<>'"]/g,
        c => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[c])
    );
}


// ==========================================================
// NORMALIZAR DATA
// ==========================================================

function normalizarData(data) {
    if (!data) return null;

    const parte = String(data).split('T')[0];

    const [ano, mes, dia] = parte.split('-');

    if (!ano || !mes || !dia) {
        return null;
    }

    return new Date(
        Number(ano),
        Number(mes) - 1,
        Number(dia)
    );
}


// ==========================================================
// CRIAR SEMANA
// ==========================================================

function criarSemana() {

    const container =
        document.getElementById('semana');

    if (!container) {
        return;
    }

    container.innerHTML = '';

    const hoje = new Date();

    // Segunda-feira da semana atual
    const diaSemana = hoje.getDay();

    const diferenca =
        diaSemana === 0
            ? -6
            : 1 - diaSemana;

    const segunda = new Date(hoje);

    segunda.setDate(
        hoje.getDate() + diferenca
    );

    const nomesDias = [
        'Segunda',
        'Terça',
        'Quarta',
        'Quinta',
        'Sexta',
        'Sábado',
        'Domingo'
    ];

    for (let i = 0; i < 7; i++) {

        const data = new Date(segunda);

        data.setDate(
            segunda.getDate() + i
        );

        const ano = data.getFullYear();
        const mes = String(
            data.getMonth() + 1
        ).padStart(2, '0');

        const dia = String(
            data.getDate()
        ).padStart(2, '0');

        const dataISO =
            `${ano}-${mes}-${dia}`;

        const treinosDoDia =
            treinos.filter(t => {
                return String(t.data_planejada)
                    .split('T')[0]
                    === dataISO;
            });

        const card =
            document.createElement('div');

        card.className = 'dia-card';

        card.innerHTML = `
            <div class="dia-nome">
                ${nomesDias[i]}
            </div>

            <div class="dia-data">
                ${String(data.getDate()).padStart(2, '0')}/${mes}
            </div>
        `;

        if (!treinosDoDia.length) {

            card.innerHTML += `
                <div class="dia-sem-treino">
                    Nenhum treino
                </div>
            `;

        } else {

            treinosDoDia.forEach(treino => {

                card.innerHTML +=
                    criarTreinoDia(treino);

            });

        }

        container.appendChild(card);
    }
}


// ==========================================================
// CARD DO TREINO
// ==========================================================

function criarTreinoDia(t) {

    const concluido =
        Boolean(t.concluido);

    return `
        <div class="treino-dia ${
            concluido
                ? 'treino-concluido'
                : ''
        }">

            <h3>
                ${escapeHtml(
                    t.treino.titulo
                )}
            </h3>

            <p>
                <strong>
                    ${escapeHtml(
                        t.treino.modalidade
                    )}
                </strong>
            </p>

            <p>
                ${escapeHtml(
                    t.treino.descricao
                )}
            </p>

            ${
                t.treino.ritmo_alvo
                    ? `
                        <p>
                            <strong>Ritmo:</strong>
                            ${escapeHtml(
                                t.treino.ritmo_alvo
                            )}
                        </p>
                    `
                    : ''
            }

            ${
                concluido
                    ? `
                        <span class="badge-concluido">
                            ✓ Concluído
                        </span>
                    `
                    : `
                        <button
                            class="btn-concluir"
                            onclick="abrirFeedback(
                                ${t.id},
                                '${String(
                                    t.treino.titulo
                                ).replace(
                                    /'/g,
                                    "\\'"
                                )}'
                            )"
                        >
                            Concluir treino
                        </button>
                    `
            }

        </div>
    `;
}


// ==========================================================
// CARREGAR DADOS
// ==========================================================

async function carregar() {

    try {

        const resMe =
            await fetch('/api/me');

        const resTreinos =
            await fetch('/api/me/treinos');

        if (
            resMe.status === 401 ||
            resTreinos.status === 401
        ) {

            window.location.href =
                '/login';

            return;
        }

        if (
            !resMe.ok ||
            !resTreinos.ok
        ) {

            throw new Error(
                'Erro ao consultar API.'
            );
        }

        const me =
            await resMe.json();

        treinos =
            await resTreinos.json();

        console.log("ME:", me);
        console.log("TREINOS:", treinos);

        // Dados do aluno
        if (
            !me.aluno
        ) {

            document
                .getElementById('subtitulo')
                .textContent =
                    'Dados do aluno não encontrados.';

            document
                .getElementById('perfil')
                .textContent =
                    'Sua conta não está vinculada a um aluno.';

            return;
        }

        document
            .getElementById('subtitulo')
            .textContent =
                `Bem-vindo, ${me.aluno.nome}! ` +
                `Nível: ${me.aluno.nivel}`;

        document
            .getElementById('perfil')
            .innerHTML = `
                Nome:
                <b>${escapeHtml(
                    me.aluno.nome
                )}</b>

                <br>

                Nível:
                <b>${escapeHtml(
                    me.aluno.nivel
                )}</b>

                <br>

                Usuário:
                <b>${escapeHtml(
                    me.usuario
                )}</b>
            `;

        atualizarResumo();

        criarSemana();

        mostrarHistorico();

    } catch (erro) {

        console.error(erro);

        document
            .getElementById('subtitulo')
            .textContent =
                'Erro ao carregar seus dados.';
    }
}


// ==========================================================
// RESUMO
// ==========================================================

function atualizarResumo() {

    const pendentes =
        treinos.filter(
            t => !t.concluido
        );

    const concluidos =
        treinos.filter(
            t => t.concluido
        );

    document
        .getElementById('total')
        .textContent =
            treinos.length;

    document
        .getElementById('pendentes')
        .textContent =
            pendentes.length;

    document
        .getElementById('concluidos')
        .textContent =
            concluidos.length;
}


// ==========================================================
// HISTÓRICO
// ==========================================================

function mostrarHistorico() {

    const container =
        document.getElementById(
            'listaConcluidos'
        );

    if (!container) {
        return;
    }

    const concluidos =
        treinos.filter(
            t => t.concluido
        );

    if (!concluidos.length) {

        container.innerHTML = `
            <p class="vazio">
                Nenhum treino concluído ainda.
            </p>
        `;

        return;
    }

    container.innerHTML =
        concluidos.map(t => `
            <div class="treino">

                <h3>
                    ${escapeHtml(
                        t.treino.titulo
                    )}
                </h3>

                <p>
                    <strong>
                        Data:
                    </strong>

                    ${escapeHtml(
                        t.data_planejada
                    )}
                </p>

                <span class="badge">
                    Concluído
                </span>

            </div>
        `).join('');
}


// ==========================================================
// MODAL DE FEEDBACK
// ==========================================================

function abrirFeedback(
    id,
    nomeTreino
) {

    treinoSelecionado = id;
    notaSelecionada = 0;

    const modal =
        document.getElementById(
            'modalFeedback'
        );

    const nome =
        document.getElementById(
            'nomeTreinoFeedback'
        );

    if (!modal) {
        return;
    }

    nome.textContent =
        `Como foi o treino "${nomeTreino}"?`;

    document
        .getElementById(
            'feedbackDificuldade'
        )
        .value = 'Moderado';

    document
        .getElementById(
            'feedbackComentario'
        )
        .value = '';

    atualizarEstrelas();

    modal.style.display = 'flex';
}


function fecharFeedback() {

    treinoSelecionado = null;
    notaSelecionada = 0;

    const modal =
        document.getElementById(
            'modalFeedback'
        );

    if (modal) {
        modal.style.display = 'none';
    }
}


function selecionarNota(nota) {

    notaSelecionada = nota;

    atualizarEstrelas();
}


function atualizarEstrelas() {

    const botoes =
        document.querySelectorAll(
            '.estrelas button'
        );

    botoes.forEach(
        (botao, indice) => {

            botao.classList.toggle(
                'selecionada',
                indice <
                    notaSelecionada
            );

        }
    );
}


// ==========================================================
// ENVIAR FEEDBACK
// ==========================================================

async function enviarFeedback() {

    if (!treinoSelecionado) {

        alert(
            'Nenhum treino selecionado.'
        );

        return;
    }

    if (
        notaSelecionada < 1 ||
        notaSelecionada > 5
    ) {

        alert(
            'Escolha uma nota de 1 a 5.'
        );

        return;
    }

    const dificuldade =
        document.getElementById(
            'feedbackDificuldade'
        ).value;

    const comentario =
        document.getElementById(
            'feedbackComentario'
        ).value;

    const resposta =
        await fetch(
            `/api/treinos/${treinoSelecionado}/concluir`,
            {
                method: 'PATCH',

                headers: {
                    'Content-Type':
                        'application/json'
                },

                body: JSON.stringify({
                    nota:
                        notaSelecionada,

                    dificuldade:
                        dificuldade,

                    comentario:
                        comentario || null
                })
            }
        );

    const dados =
        await resposta
            .json()
            .catch(() => ({}));

    if (!resposta.ok) {

        alert(
            dados.detail ||
            'Não foi possível concluir o treino.'
        );

        return;
    }

    const treino =
        treinos.find(
            t =>
                t.id ===
                treinoSelecionado
        );

    if (treino) {
        treino.concluido = true;
    }

    fecharFeedback();

    atualizarResumo();

    criarSemana();

    mostrarHistorico();
}


// ==========================================================
// SAIR
// ==========================================================

async function sair() {

    await fetch(
        '/api/logout',
        {
            method: 'POST'
        }
    );

    window.location.href =
        '/login';
}


// ==========================================================
// INICIAR
// ==========================================================

carregar();