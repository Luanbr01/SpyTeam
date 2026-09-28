(() => {
    const navigation = document.getElementById('professor-navigation');
    const sidebar = navigation?.closest('.professor-sidebar');
    const toggle = sidebar?.querySelector('.professor-menu-toggle');
    if (!sidebar || !toggle) return;
    const mobile = window.matchMedia('(max-width: 780px)');
    const label = toggle.querySelector('span');
    function setOpen(open) {
        sidebar.classList.toggle('menu-open', open);
        toggle.setAttribute('aria-expanded', String(open));
        label.textContent = open ? 'Fechar' : 'Menu';
    }
    toggle.hidden = false;
    sidebar.classList.add('menu-ready');
    toggle.addEventListener('click', () => setOpen(!sidebar.classList.contains('menu-open')));
    sidebar.addEventListener('keydown', event => {
        if (event.key === 'Escape' && mobile.matches && sidebar.classList.contains('menu-open')) {
            setOpen(false);
            toggle.focus();
        }
    });
    navigation.addEventListener('click', event => {
        if (mobile.matches && event.target.closest('a')) setOpen(false);
    });
    mobile.addEventListener('change', () => {
        const focusWasInside = navigation.contains(document.activeElement);
        setOpen(false);
        if (mobile.matches && focusWasInside) toggle.focus();
    });
})();
