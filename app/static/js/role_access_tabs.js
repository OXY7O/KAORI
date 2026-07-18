(() => {
    const ROOT_SELECTOR = '[data-role-access-tabs]'

    function initializeRoleAccessTabs(root) {
        if (!(root instanceof HTMLElement) || root.dataset.roleAccessTabsReady === 'true') {
            return
        }

        root.dataset.roleAccessTabsReady = 'true'
        const buttons = Array.from(root.querySelectorAll('[data-role-access-tab]'))
        const panels = Array.from(root.querySelectorAll('[data-role-access-panel]'))

        function activate(tabName, { updateHash = true } = {}) {
            const targetName = buttons.some((button) => button.dataset.roleAccessTab === tabName)
                ? tabName
                : 'registry'

            buttons.forEach((button) => {
                const active = button.dataset.roleAccessTab === targetName
                button.setAttribute('aria-selected', active ? 'true' : 'false')
                button.classList.toggle('bg-kaori-primary', active)
                button.classList.toggle('text-white', active)
                button.classList.toggle('text-content-secondary', !active)
                button.classList.toggle('hover:bg-surface-hover', !active)
                button.classList.toggle('hover:text-kaori-primary', !active)
            })

            panels.forEach((panel) => {
                panel.hidden = panel.dataset.roleAccessPanel !== targetName
            })

            if (updateHash) {
                const nextHash = targetName === 'matrix' ? '#role-permission-matrix' : '#role-registry'
                window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${nextHash}`)
            }

            if (window.renderKaoriIcons) {
                window.renderKaoriIcons()
            }
        }

        buttons.forEach((button) => {
            button.addEventListener('click', () => activate(button.dataset.roleAccessTab || 'registry'))
        })

        const initialTab = window.location.hash === '#role-permission-matrix' ? 'matrix' : 'registry'
        activate(initialTab, { updateHash: false })
    }

    function initializeAll() {
        document.querySelectorAll(ROOT_SELECTOR).forEach(initializeRoleAccessTabs)
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeAll, { once: true })
    } else {
        initializeAll()
    }

    document.addEventListener('htmx:afterSwap', initializeAll)
})()
