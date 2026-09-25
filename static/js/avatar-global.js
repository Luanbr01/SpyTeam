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
                if (dados.foto_perfil_url) {
                    el.innerHTML = '';
                    const img = document.createElement('img');
                    img.src = dados.foto_perfil_url;
                    img.alt = 'Foto de perfil';
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
