(function () {
    'use strict';

    async function carregarAvatar() {
        try {
            const resposta = await fetch('/api/me');
            if (!resposta.ok) return;

            const dados = await resposta.json();
            const nome = dados.aluno?.nome || dados.nome || dados.usuario || 'SPY TEAM';
            const inicial = String(nome).trim().charAt(0).toUpperCase() || 'S';

            document.querySelectorAll('.sidebar-avatar, .top-avatar').forEach(el => {
                el.style.overflow = 'hidden';
                el.style.padding = '0';
                el.style.width = '34px';
                el.style.height = '34px';
                el.style.minWidth = '34px';
                el.style.minHeight = '34px';
                el.style.maxWidth = '34px';
                el.style.maxHeight = '34px';
                el.style.flexBasis = '34px';
                el.style.flexShrink = '0';

                if (dados.foto_perfil_url) {
                    el.replaceChildren();

                    const img = document.createElement('img');
                    img.src = dados.foto_perfil_url;
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

                    el.appendChild(img);
                    el.classList.add('has-photo');
                } else {
                    el.textContent = inicial;
                    el.classList.remove('has-photo');
                }
            });

            document.querySelectorAll('#sidebarName').forEach(el => {
                el.textContent = nome;
            });
        } catch (_) {
            // O avatar é apenas aprimoramento visual; não interfere na página.
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', carregarAvatar, {once: true});
    } else {
        carregarAvatar();
    }
})();
