;(() => {
    const rootSelector = '[data-secret-reveal-workspace]'
    const tabSelector = '[data-secret-reveal-tab]'
    const panelSelector = '[data-secret-reveal-panel]'
    let pollTimer = null

    const renderIcons = () => {
        window.renderKaoriIcons?.()
        if (!window.renderKaoriIcons && window.lucide) window.lucide.createIcons()
    }

    const pollActivePanel = (panel) => {
        if (!(panel instanceof HTMLElement) || panel.hidden || document.hidden) return
        const owner = panel.matches('[data-reveal-poll-owner]')
            ? panel
            : panel.querySelector('[data-reveal-poll-owner]')
        const url = owner?.dataset.revealPollUrl
        const target = owner?.dataset.revealPollTarget
        if (!url || !target || !window.htmx) return
        window.htmx.ajax('GET', url, { target, swap: 'outerHTML' })
    }

    const schedulePolling = (panel) => {
        if (pollTimer) window.clearInterval(pollTimer)
        pollTimer = null
        if (!panel?.querySelector?.('[data-reveal-poll-owner]') && !panel?.matches?.('[data-reveal-poll-owner]')) return
        pollTimer = window.setInterval(() => pollActivePanel(panel), 4000)
    }

    const selectTab = (root, key, focus = false) => {
        const tabs = [...root.querySelectorAll(tabSelector)]
        const panels = [...root.querySelectorAll(panelSelector)]
        let activePanel = null
        tabs.forEach((tab) => {
            const selected = tab.dataset.secretRevealTab === key
            tab.setAttribute('aria-selected', selected ? 'true' : 'false')
            tab.tabIndex = selected ? 0 : -1
            tab.classList.toggle('bg-surface-card', selected)
            tab.classList.toggle('text-kaori-primary', selected)
            tab.classList.toggle('shadow-sm', selected)
            tab.classList.toggle('text-content-muted', !selected)
            if (selected && focus) tab.focus()
        })
        panels.forEach((panel) => {
            const selected = panel.dataset.secretRevealPanel === key
            panel.hidden = !selected
            if (selected) activePanel = panel
        })
        schedulePolling(activePanel)
        renderIcons()
    }

    const initialise = (root) => {
        if (!(root instanceof HTMLElement) || root.dataset.revealTabsReady === 'true') return
        root.dataset.revealTabsReady = 'true'
        const tabs = [...root.querySelectorAll(tabSelector)]
        tabs.forEach((tab, index) => {
            tab.addEventListener('click', () => selectTab(root, tab.dataset.secretRevealTab))
            tab.addEventListener('keydown', (event) => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
                event.preventDefault()
                let nextIndex = index
                if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length
                if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length
                if (event.key === 'Home') nextIndex = 0
                if (event.key === 'End') nextIndex = tabs.length - 1
                selectTab(root, tabs[nextIndex].dataset.secretRevealTab, true)
            })
        })
        selectTab(root, 'new')
    }

    const boot = (scope = document) => {
        if (scope.matches?.(rootSelector)) initialise(scope)
        scope.querySelectorAll?.(rootSelector).forEach(initialise)
    }
    document.addEventListener('htmx:load', (event) => boot(event.detail?.elt || document))
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => boot())
    else boot()
})()
