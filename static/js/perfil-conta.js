// ============================================================
// PERFIL-CONTA.JS
// Dados pessoais, e-mail, foto e senha para aluno/professor.
// ============================================================

(function () {
    'use strict';

    let contaAtual = null;

    function primeiraLetra(valor) {
        const texto = String(valor || '').trim();
        return texto ? texto.charAt(0).toUpperCase() : 'S';
    }

    function setMensagem(id, texto, tipo = '') {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = texto || '';
        el.className = 'account-inline-message';
        if (tipo) el.classList.add(tipo);
    }

    function aplicarAvatar(elemento, conta) {
        if (!elemento || !conta) return;

        const nome = conta.aluno?.nome || conta.nome || conta.usuario || 'SPY TEAM';
        const inicial = primeiraLetra(nome);
        const url = conta.foto_perfil_url || '';

        const ehPequeno =
            elemento.classList.contains('sidebar-avatar') ||
            elemento.classList.contains('top-avatar');

        const ehPerfil = elemento.classList.contains('student-profile-avatar');

        elemento.style.overflow = 'hidden';
        elemento.style.padding = '0';
        elemento.style.flexShrink = '0';

        if (ehPequeno) {
            elemento.style.width = '34px';
            elemento.style.height = '34px';
            elemento.style.minWidth = '34px';
            elemento.style.minHeight = '34px';
            elemento.style.maxWidth = '34px';
            elemento.style.maxHeight = '34px';
            elemento.style.flexBasis = '34px';
        } else if (ehPerfil) {
            elemento.style.width = '76px';
            elemento.style.height = '76px';
            elemento.style.minWidth = '76px';
            elemento.style.minHeight = '76px';
            elemento.style.maxWidth = '76px';
            elemento.style.maxHeight = '76px';
            elemento.style.flexBasis = '76px';
        }

        if (url) {
            elemento.replaceChildren();

            const img = document.createElement('img');
            img.src = url;
            img.alt = 'Foto de perfil';
            img.decoding = 'async';

            Object.assign(img.style, {
                width: '100%',
                height: '100%',
                minWidth: '0',
                minHeight: '0',
                maxWidth: '100%',
                maxHeight: '100%',
                display: 'block',
                objectFit: 'cover',
                objectPosition: 'center',
                borderRadius: 'inherit',
                position: 'static'
            });

            elemento.appendChild(img);
            elemento.classList.add('has-photo');
        } else {
            elemento.textContent = inicial;
            elemento.classList.remove('has-photo');
        }
    }

    function preencherConta(conta) {
        contaAtual = conta;

        const ehAluno = conta.tipo === 'aluno' && conta.aluno;
        const nome = ehAluno
            ? conta.aluno.nome
            : (conta.nome || conta.usuario || 'Professor');

        const resumo = ehAluno
            ? `${conta.aluno.nivel || 'Nível não informado'} • ${
                Array.isArray(conta.aluno.modalidades) && conta.aluno.modalidades.length
                    ? conta.aluno.modalidades.join(' • ')
                    : (conta.aluno.modalidade || 'Modalidade não informada')
            }`
            : 'Professor • SPY TEAM';

        const valores = {
            profileName: nome,
            profileSummary: resumo,
            profileFullName: nome,
            profileUsername: conta.usuario || '—',
            profileEmail: conta.email || 'Não informado',
            editNome: nome,
            editUsuario: conta.usuario || '',
            currentEmailValue: conta.email || 'Não cadastrado'
        };

        Object.entries(valores).forEach(([id, valor]) => {
            const el = document.getElementById(id);
            if (!el) return;
            if ('value' in el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                el.value = valor;
            } else {
                el.textContent = valor;
            }
        });

        const badge = document.getElementById('currentEmailBadge');
        if (badge) {
            if (conta.email && conta.email_verificado) {
                badge.textContent = '✓ Verificado';
                badge.className = 'account-email-badge verified';
            } else {
                badge.textContent = 'Não verificado';
                badge.className = 'account-email-badge pending';
            }
        }

        const pendingBox = document.getElementById('pendingEmailBox');
        const pendingText = document.getElementById('pendingEmailText');
        if (pendingBox && pendingText) {
            if (conta.email_pendente) {
                pendingBox.hidden = false;
                pendingText.textContent = `Aguardando confirmação de ${conta.email_pendente}.`;
            } else {
                pendingBox.hidden = true;
                pendingText.textContent = '';
            }
        }

        ['profileAvatar', 'topAvatar', 'sidebarAvatar'].forEach(id => {
            aplicarAvatar(document.getElementById(id), conta);
        });

        const sidebarName = document.getElementById('sidebarName');
        if (sidebarName) sidebarName.textContent = nome;

        const remover = document.getElementById('btnRemoverFoto');
        if (remover) remover.hidden = !conta.foto_perfil;
    }

    async function carregarConta() {
        const resposta = await fetch('/api/me');

        if (resposta.status === 401) {
            window.location.href = '/login';
            return null;
        }

        if (!resposta.ok) {
            throw new Error('Não foi possível carregar os dados da conta.');
        }

        const conta = await resposta.json();
        preencherConta(conta);
        return conta;
    }

    function configurarDadosPessoais() {
        const form = document.getElementById('formDadosPessoais');
        if (!form) return;

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            setMensagem('mensagemDados', 'Salvando...');

            const botao = form.querySelector('button[type="submit"]');
            if (botao) botao.disabled = true;

            try {
                const resposta = await fetch('/api/me/perfil', {
                    method: 'PATCH',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        nome: document.getElementById('editNome').value.trim(),
                        usuario: document.getElementById('editUsuario').value.trim()
                    })
                });

                const dados = await resposta.json().catch(() => ({}));

                if (!resposta.ok) {
                    setMensagem('mensagemDados', dados.detail || 'Não foi possível salvar os dados.', 'error');
                    return;
                }

                setMensagem('mensagemDados', dados.mensagem || 'Dados atualizados.', 'success');
                await carregarConta();
            } catch (erro) {
                console.error(erro);
                setMensagem('mensagemDados', 'Não foi possível conectar ao servidor.', 'error');
            } finally {
                if (botao) botao.disabled = false;
            }
        });
    }

    function configurarTrocaEmail() {
        const form = document.getElementById('formTrocarEmail');
        if (!form) return;

        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const email = document.getElementById('novoEmail').value.trim().toLowerCase();
            const confirmar = document.getElementById('confirmarNovoEmail').value.trim().toLowerCase();
            const senha = document.getElementById('senhaEmail').value;

            if (email !== confirmar) {
                setMensagem('mensagemEmail', 'Os e-mails não conferem.', 'error');
                return;
            }

            setMensagem('mensagemEmail', 'Enviando confirmação...');
            const botao = form.querySelector('button[type="submit"]');
            if (botao) botao.disabled = true;

            try {
                const resposta = await fetch('/api/me/email/troca', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        email,
                        confirmar_email: confirmar,
                        senha_atual: senha
                    })
                });

                const dados = await resposta.json().catch(() => ({}));

                if (!resposta.ok) {
                    setMensagem('mensagemEmail', dados.detail || 'Não foi possível solicitar a troca.', 'error');
                    return;
                }

                setMensagem('mensagemEmail', dados.mensagem || 'Confirmação enviada.', 'success');
                document.getElementById('senhaEmail').value = '';
                await carregarConta();
            } catch (erro) {
                console.error(erro);
                setMensagem('mensagemEmail', 'Não foi possível conectar ao servidor.', 'error');
            } finally {
                if (botao) botao.disabled = false;
            }
        });
    }

    function configurarFoto() {
        const input = document.getElementById('fotoPerfilInput');
        const remover = document.getElementById('btnRemoverFoto');

        if (input) {
            input.addEventListener('change', async () => {
                const arquivo = input.files?.[0];
                if (!arquivo) return;

                if (arquivo.size > 3 * 1024 * 1024) {
                    setMensagem('mensagemFoto', 'A foto deve ter no máximo 3 MB.', 'error');
                    input.value = '';
                    return;
                }

                const permitido = ['image/png', 'image/jpeg', 'image/webp'];
                if (!permitido.includes(arquivo.type)) {
                    setMensagem('mensagemFoto', 'Use uma imagem PNG, JPG ou WEBP.', 'error');
                    input.value = '';
                    return;
                }

                const dados = new FormData();
                dados.append('foto', arquivo);
                setMensagem('mensagemFoto', 'Enviando foto...');

                try {
                    const resposta = await fetch('/api/me/foto', {
                        method: 'POST',
                        body: dados
                    });

                    const retorno = await resposta.json().catch(() => ({}));

                    if (!resposta.ok) {
                        setMensagem('mensagemFoto', retorno.detail || 'Não foi possível atualizar a foto.', 'error');
                        return;
                    }

                    setMensagem('mensagemFoto', retorno.mensagem || 'Foto atualizada.', 'success');
                    await carregarConta();
                } catch (erro) {
                    console.error(erro);
                    setMensagem('mensagemFoto', 'Não foi possível conectar ao servidor.', 'error');
                } finally {
                    input.value = '';
                }
            });
        }

        if (remover) {
            remover.addEventListener('click', async () => {
                setMensagem('mensagemFoto', 'Removendo foto...');

                try {
                    const resposta = await fetch('/api/me/foto', {method: 'DELETE'});
                    const dados = await resposta.json().catch(() => ({}));

                    if (!resposta.ok) {
                        setMensagem('mensagemFoto', dados.detail || 'Não foi possível remover a foto.', 'error');
                        return;
                    }

                    setMensagem('mensagemFoto', dados.mensagem || 'Foto removida.', 'success');
                    await carregarConta();
                } catch (erro) {
                    console.error(erro);
                    setMensagem('mensagemFoto', 'Não foi possível conectar ao servidor.', 'error');
                }
            });
        }
    }

    function configurarOlhinhosSenha() {
        document.querySelectorAll('[data-password-target]').forEach(botao => {
            if (botao.dataset.passwordConfigured === 'true') return;
            botao.dataset.passwordConfigured = 'true';

            botao.addEventListener('click', () => {
                const input = document.getElementById(botao.dataset.passwordTarget);
                if (!input) return;

                const mostrar = input.type === 'password';
                input.type = mostrar ? 'text' : 'password';
                botao.classList.toggle('is-visible', mostrar);
                botao.setAttribute('aria-label', mostrar ? 'Ocultar senha' : 'Mostrar senha');
                botao.setAttribute('title', mostrar ? 'Ocultar senha' : 'Mostrar senha');
            });
        });
    }

    function configurarSenha() {
        const form = document.getElementById('formAlterarSenha');
        if (!form) return;

        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const senhaAtual = document.getElementById('senhaAtual').value;
            const novaSenha = document.getElementById('novaSenha').value;
            const confirmar = document.getElementById('confirmarNovaSenha').value;

            if (novaSenha.length < 4) {
                setMensagem('mensagemAlterarSenha', 'A nova senha precisa ter pelo menos 4 caracteres.', 'error');
                return;
            }

            if (novaSenha !== confirmar) {
                setMensagem('mensagemAlterarSenha', 'A confirmação da nova senha não confere.', 'error');
                return;
            }

            const botao = document.getElementById('btnAlterarSenha');
            if (botao) botao.disabled = true;
            setMensagem('mensagemAlterarSenha', 'Alterando senha...');

            try {
                const resposta = await fetch('/api/me/senha', {
                    method: 'PATCH',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        senha_atual: senhaAtual,
                        nova_senha: novaSenha,
                        confirmar_senha: confirmar
                    })
                });

                const dados = await resposta.json().catch(() => ({}));

                if (!resposta.ok) {
                    setMensagem('mensagemAlterarSenha', dados.detail || 'Não foi possível alterar a senha.', 'error');
                    return;
                }

                form.reset();
                setMensagem('mensagemAlterarSenha', dados.mensagem || 'Senha alterada com sucesso.', 'success');

                setTimeout(() => {
                    window.location.href = dados.redirect || '/login';
                }, 1000);
            } catch (erro) {
                console.error(erro);
                setMensagem('mensagemAlterarSenha', 'Não foi possível conectar ao servidor.', 'error');
            } finally {
                if (botao) botao.disabled = false;
            }
        });
    }

    async function iniciar() {
        configurarOlhinhosSenha();
        configurarDadosPessoais();
        configurarTrocaEmail();
        configurarFoto();
        configurarSenha();

        try {
            await carregarConta();
        } catch (erro) {
            console.error(erro);
            setMensagem('mensagemDados', 'Não foi possível carregar sua conta.', 'error');
        }
    }

    iniciar();
})();
