let treinos = [];
let treinoSelecionado = null;
let notaSelecionada = 0;
let usuarioAtual = null;


// ==========================================================
// UTILITÁRIOS
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

function normalizarData(data) {
    if (!data) return null;

    const parte = String(data).split('T')[0];
    const [ano, mes, dia] = parte.split('-');

    if (!ano || !mes || !dia) return null;

    return new Date(
        Number(ano),
        Number(mes) - 1,
        Number(dia)
    );
}

function formatarData(data) {
    const d = normalizarData(data);

    if (!d) return 'Data não informada';

    return new Intl.DateTimeFormat(
        'pt-BR',
        {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        }
    ).format(d);
}

function paginaAtual() {
    return document.body.dataset.alunoPage || 'dashboard';
}

function primeiraLetra(nome) {
    const valor = String(nome || 'A').trim();
    return valor ? valor.charAt(0).toUpperCase() : 'A';
}

function preencherIdentidade(me) {
    if (!me || !me.aluno) return;

    const inicial = primeiraLetra(me.aluno.nome);

    const sidebarName =
        document.getElementById('sidebarName');

    const sidebarAvatar =
        document.getElementById('sidebarAvatar');

    const topAvatar =
        document.getElementById('topAvatar');

    if (sidebarName) {
        sidebarName.textContent = me.aluno.nome;
    }

    if (sidebarAvatar) {
        sidebarAvatar.textContent = inicial;
    }

    if (topAvatar) {
        topAvatar.textContent = inicial;
    }
}


// ==========================================================
// SEMANA / DASHBOARD
// ==========================================================

function criarSemana() {
    const container =
        document.getElementById('semana');

    if (!container) return;

    container.innerHTML = '';

    const hoje = new Date();
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
        'Sexta'
    ];

    for (let i = 0; i < 5; i++) {
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
                return String(
                    t.data_planejada
                ).split('T')[0] === dataISO;
            });

        const card =
            document.createElement('div');

        card.className = 'dia-card';

        card.innerHTML = `
            <div class="dia-nome">
                ${nomesDias[i]}
            </div>

            <div class="dia-data">
                ${dia}/${mes}
            </div>
        `;

        if (!treinosDoDia.length) {
            card.innerHTML += `
                <div class="dia-sem-treino">
                    Nenhum treino
                </div>
            `;
        } else {
            treinosDoDia.forEach(
                treino => {
                    card.innerHTML +=
                        criarTreinoDia(treino);
                }
            );
        }

        container.appendChild(card);
    }
}

function criarTreinoDia(t) {
    const concluido = Boolean(t.concluido);

    return `
        <button
            type="button"
            class="treino-dia treino-dia-clickable ${
                concluido ? 'treino-concluido' : ''
            }"
            onclick="abrirDetalhesTreino(${t.id})"
            aria-label="Abrir detalhes do treino ${escapeHtml(t.treino.titulo)}"
        >
            <span class="treino-dia-topo">
                <span class="treino-modalidade-mini">
                    ${escapeHtml(t.treino.modalidade)}
                </span>
                <span class="treino-status-mini ${concluido ? 'feito' : 'pendente'}">
                    ${concluido ? '✓ Feito' : 'Pendente'}
                </span>
            </span>

            <strong class="treino-dia-titulo">
                ${escapeHtml(t.treino.titulo)}
            </strong>

            <span class="treino-dia-abrir">Ver detalhes →</span>
        </button>
    `;
}

function abrirDetalhesTreino(id) {
    const item = treinos.find(t => t.id === id);
    if (!item) return;

    treinoSelecionado = id;

    const modal = document.getElementById('modalTreinoDetalhes');
    if (!modal) return;

    const treino = item.treino || {};

    const titulo = document.getElementById('detalheTreinoTitulo');
    const modalidade = document.getElementById('detalheTreinoModalidade');
    const data = document.getElementById('detalheTreinoData');
    const descricao = document.getElementById('detalheTreinoDescricao');
    const ritmo = document.getElementById('detalheTreinoRitmo');
    const acao = document.getElementById('detalheTreinoAcao');

    if (titulo) titulo.textContent = treino.titulo || 'Treino';
    if (modalidade) modalidade.textContent = treino.modalidade || '-';
    if (data) data.textContent = formatarData(item.data_planejada);
    if (descricao) descricao.textContent = treino.descricao || 'Sem descrição.';

    if (ritmo) {
        if (treino.ritmo_alvo) {
            ritmo.closest('.detalhe-treino-bloco').style.display = 'block';
            ritmo.textContent = treino.ritmo_alvo;
        } else {
            ritmo.closest('.detalhe-treino-bloco').style.display = 'none';
        }
    }

    if (acao) {
        if (item.concluido) {
            acao.innerHTML = '<span class="badge-concluido detalhe-concluido">✓ Treino concluído</span>';
        } else {
            acao.innerHTML = `
                <button class="btn btn-primary detalhe-btn-concluir" onclick="concluirPeloDetalhe()">
                    Concluir treino
                </button>
            `;
        }
    }

    modal.style.display = 'flex';
    document.body.classList.add('modal-aberto');
}

function fecharDetalhesTreino() {
    const modal = document.getElementById('modalTreinoDetalhes');
    if (modal) modal.style.display = 'none';
    document.body.classList.remove('modal-aberto');
}

function concluirPeloDetalhe() {
    const item = treinos.find(t => t.id === treinoSelecionado);
    if (!item || item.concluido) return;

    const id = item.id;
    const titulo = item.treino?.titulo || 'Treino';

    fecharDetalhesTreino();
    abrirFeedback(id, titulo);
}


function atualizarResumo() {
    const total =
        document.getElementById('total');

    const pendentes =
        document.getElementById('pendentes');

    const concluidos =
        document.getElementById('concluidos');

    const listaPendentes =
        treinos.filter(
            t => !t.concluido
        );

    const listaConcluidos =
        treinos.filter(
            t => t.concluido
        );

    if (total) {
        total.textContent =
            treinos.length;
    }

    if (pendentes) {
        pendentes.textContent =
            listaPendentes.length;
    }

    if (concluidos) {
        concluidos.textContent =
            listaConcluidos.length;
    }
}


// ==========================================================
// HISTÓRICO
// ==========================================================

function mostrarHistorico() {
    const container =
        document.getElementById(
            'listaConcluidos'
        );

    if (!container) return;

    const concluidos =
        treinos
            .filter(t => t.concluido)
            .sort((a, b) => {
                const dataA =
                    normalizarData(
                        a.data_planejada
                    );

                const dataB =
                    normalizarData(
                        b.data_planejada
                    );

                return (
                    (dataB?.getTime() || 0) -
                    (dataA?.getTime() || 0)
                );
            });

    const total =
        document.getElementById(
            'historicoTotal'
        );

    if (total) {
        total.textContent =
            concluidos.length;
    }

    if (!concluidos.length) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">✓</span>
                <h3>Nenhum treino concluído ainda</h3>
                <p>
                    Quando você finalizar seus treinos,
                    eles aparecerão aqui.
                </p>
                <a class="btn btn-primary" href="/aluno">
                    Ver meus treinos
                </a>
            </div>
        `;
        return;
    }

    container.innerHTML =
        concluidos.map(t => {
            const nota =
                Number(t.feedback_nota || 0);

            const estrelas =
                nota > 0
                    ? '★'.repeat(nota) +
                      '☆'.repeat(
                          Math.max(
                              0,
                              5 - nota
                          )
                      )
                    : 'Sem avaliação';

            return `
                <article class="history-item">
                    <div class="history-item-icon">
                        ✓
                    </div>

                    <div class="history-item-main">
                        <div class="history-item-heading">
                            <div>
                                <span class="history-modality">
                                    ${escapeHtml(
                                        t.treino.modalidade
                                    )}
                                </span>

                                <h3>
                                    ${escapeHtml(
                                        t.treino.titulo
                                    )}
                                </h3>
                            </div>

                            <span class="history-date">
                                ${formatarData(
                                    t.data_planejada
                                )}
                            </span>
                        </div>

                        <p class="history-description">
                            ${escapeHtml(
                                t.treino.descricao
                            )}
                        </p>

                        <div class="history-meta">
                            <span class="history-chip success">
                                ✓ Concluído
                            </span>

                            ${
                                t.feedback_dificuldade
                                    ? `
                                        <span class="history-chip">
                                            Dificuldade:
                                            ${escapeHtml(
                                                t.feedback_dificuldade
                                            )}
                                        </span>
                                    `
                                    : ''
                            }

                            <span class="history-stars">
                                ${estrelas}
                            </span>
                        </div>

                        ${
                            t.feedback_comentario
                                ? `
                                    <div class="history-feedback">
                                        <strong>Seu feedback</strong>
                                        <p>
                                            ${escapeHtml(
                                                t.feedback_comentario
                                            )}
                                        </p>
                                    </div>
                                `
                                : ''
                        }
                    </div>
                </article>
            `;
        }).join('');
}


// ==========================================================
// PERFIL
// ==========================================================

function mostrarPerfil(me) {
    if (!me || !me.aluno) return;

    const aluno = me.aluno;
    const inicial =
        primeiraLetra(aluno.nome);

    const campos = {
        profileAvatar: inicial,
        profileName: aluno.nome,
        profileSummary:
            `${aluno.nivel || 'Nível não informado'} • ${
                (Array.isArray(aluno.modalidades) && aluno.modalidades.length
                    ? aluno.modalidades.join(' • ')
                    : (aluno.modalidade || 'Modalidade não informada'))
            }`,
        profileFullName: aluno.nome,
        profileUsername: me.usuario,
        profileEmail:
            me.email || 'Não informado',
        profileLevel:
            aluno.nivel ||
            'Não informado',
        profileModality:
            (Array.isArray(aluno.modalidades) && aluno.modalidades.length
                ? aluno.modalidades.join(' • ')
                : (aluno.modalidade || 'Não informada'))
    };

    Object.entries(campos)
        .forEach(
            ([id, valor]) => {
                const elemento =
                    document.getElementById(id);

                if (elemento) {
                    elemento.textContent =
                        valor;
                }
            }
        );
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

    if (!modal) return;

    if (nome) {
        nome.textContent =
            `Como foi o treino "${nomeTreino}"?`;
    }

    const dificuldade =
        document.getElementById(
            'feedbackDificuldade'
        );

    const comentario =
        document.getElementById(
            'feedbackComentario'
        );

    if (dificuldade) {
        dificuldade.value =
            'Moderado';
    }

    if (comentario) {
        comentario.value = '';
    }

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
        modal.style.display =
            'none';
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
                indice < notaSelecionada
            );
        }
    );
}

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
        treino.feedback_nota =
            notaSelecionada;
        treino.feedback_dificuldade =
            dificuldade;
        treino.feedback_comentario =
            comentario || null;
    }

    fecharFeedback();
    atualizarResumo();
    criarSemana();
}




// ==========================================================
// SEGURANÇA / ALTERAR SENHA
// ==========================================================

function alternarVisibilidadeSenha(
    input,
    botao
) {
    const vaiMostrar =
        input.type === 'password';

    input.type =
        vaiMostrar
            ? 'text'
            : 'password';

    botao.classList.toggle(
        'is-visible',
        vaiMostrar
    );

    botao.setAttribute(
        'aria-label',
        vaiMostrar
            ? 'Ocultar senha'
            : 'Mostrar senha'
    );

    botao.setAttribute(
        'title',
        vaiMostrar
            ? 'Ocultar senha'
            : 'Mostrar senha'
    );
}


function configurarOlhinhosSenha() {
    document
        .querySelectorAll(
            '[data-password-target]'
        )
        .forEach(botao => {
            if (
                botao.dataset
                    .passwordConfigured
                === 'true'
            ) {
                return;
            }

            botao.dataset
                .passwordConfigured =
                'true';

            botao.addEventListener(
                'click',
                () => {
                    const input =
                        document.getElementById(
                            botao.dataset
                                .passwordTarget
                        );

                    if (!input) return;

                    alternarVisibilidadeSenha(
                        input,
                        botao
                    );
                }
            );
        });
}


function mostrarMensagemSenha(
    texto,
    tipo = ''
) {
    const mensagem =
        document.getElementById(
            'mensagemAlterarSenha'
        );

    if (!mensagem) return;

    mensagem.textContent = texto;
    mensagem.className =
        'password-message';

    if (tipo) {
        mensagem.classList.add(tipo);
    }
}


function configurarFormularioSenha() {
    const form =
        document.getElementById(
            'formAlterarSenha'
        );

    if (!form) return;

    configurarOlhinhosSenha();

    if (
        form.dataset.configured
        === 'true'
    ) {
        return;
    }

    form.dataset.configured = 'true';

    form.addEventListener(
        'submit',
        async event => {
            event.preventDefault();

            const senhaAtual =
                document.getElementById(
                    'senhaAtual'
                ).value;

            const novaSenha =
                document.getElementById(
                    'novaSenha'
                ).value;

            const confirmar =
                document.getElementById(
                    'confirmarNovaSenha'
                ).value;

            const botao =
                document.getElementById(
                    'btnAlterarSenha'
                );

            if (novaSenha.length < 4) {
                mostrarMensagemSenha(
                    'A nova senha precisa ter pelo menos 4 caracteres.',
                    'error'
                );
                return;
            }

            if (
                novaSenha
                !== confirmar
            ) {
                mostrarMensagemSenha(
                    'A confirmação da nova senha não confere.',
                    'error'
                );
                return;
            }

            mostrarMensagemSenha(
                'Alterando senha...'
            );

            if (botao) {
                botao.disabled = true;
                botao.textContent =
                    'Alterando...';
            }

            try {
                const resposta =
                    await fetch(
                        '/api/me/senha',
                        {
                            method: 'PATCH',

                            headers: {
                                'Content-Type':
                                    'application/json'
                            },

                            body: JSON.stringify({
                                senha_atual:
                                    senhaAtual,

                                nova_senha:
                                    novaSenha,

                                confirmar_senha:
                                    confirmar
                            })
                        }
                    );

                const dados =
                    await resposta
                        .json()
                        .catch(() => ({}));

                if (!resposta.ok) {
                    mostrarMensagemSenha(
                        dados.detail ||
                        'Não foi possível alterar a senha.',
                        'error'
                    );
                    return;
                }

                form.reset();

                document
                    .querySelectorAll(
                        '[data-password-target]'
                    )
                    .forEach(toggle => {
                        const input =
                            document.getElementById(
                                toggle.dataset
                                    .passwordTarget
                            );

                        if (input) {
                            input.type =
                                'password';
                        }

                        toggle.classList.remove(
                            'is-visible'
                        );
                    });

                mostrarMensagemSenha(
                    dados.mensagem ||
                    'Senha alterada com sucesso. Entre novamente.',
                    'success'
                );

                setTimeout(() => {
                    window.location.href =
                        dados.redirect || '/login';
                }, 1200);

            } catch (erro) {
                console.error(erro);

                mostrarMensagemSenha(
                    'Não foi possível conectar ao servidor.',
                    'error'
                );

            } finally {
                if (botao) {
                    botao.disabled = false;
                    botao.textContent =
                        'Alterar senha';
                }
            }
        }
    );
}


// ==========================================================
// CARREGAMENTO
// ==========================================================

async function obterUsuario() {
    const resposta =
        await fetch('/api/me');

    if (resposta.status === 401) {
        window.location.href =
            '/login';

        return null;
    }

    if (!resposta.ok) {
        throw new Error(
            'Erro ao consultar usuário.'
        );
    }

    return await resposta.json();
}

async function obterTreinos() {
    const resposta =
        await fetch('/api/me/treinos');

    if (resposta.status === 401) {
        window.location.href =
            '/login';

        return null;
    }

    if (!resposta.ok) {
        throw new Error(
            'Erro ao consultar treinos.'
        );
    }

    return await resposta.json();
}

async function carregar() {
    try {
        const pagina =
            paginaAtual();

        usuarioAtual =
            await obterUsuario();

        if (!usuarioAtual) return;

        preencherIdentidade(
            usuarioAtual
        );

        if (!usuarioAtual.aluno) {
            const subtitulo =
                document.getElementById(
                    'subtitulo'
                );

            if (subtitulo) {
                subtitulo.textContent =
                    'Sua conta não está vinculada a um aluno.';
            }

            return;
        }

        if (pagina === 'perfil') {
            mostrarPerfil(
                usuarioAtual
            );

            configurarFormularioSenha();

            return;
        }

        treinos =
            await obterTreinos();

        if (!treinos) return;

        if (pagina === 'historico') {
            mostrarHistorico();
            return;
        }

        const titulo =
            document.getElementById(
                'titulo'
            );

        const subtitulo =
            document.getElementById(
                'subtitulo'
            );

        if (titulo) {
            titulo.textContent =
                `Olá, ${usuarioAtual.aluno.nome} 👋`;
        }

        if (subtitulo) {
            subtitulo.textContent =
                `Aqui está seu treinamento de hoje. Nível: ${
                    usuarioAtual.aluno.nivel
                }`;
        }

        atualizarResumo();
        criarSemana();

    } catch (erro) {
        console.error(erro);

        const subtitulo =
            document.getElementById(
                'subtitulo'
            );

        if (subtitulo) {
            subtitulo.textContent =
                'Erro ao carregar seus dados.';
        }

        const lista =
            document.getElementById(
                'listaConcluidos'
            );

        if (lista) {
            lista.innerHTML =
                '<p class="vazio">Erro ao carregar o histórico.</p>';
        }
    }
}

carregar();
