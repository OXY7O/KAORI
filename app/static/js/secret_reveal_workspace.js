;(() => {
    const rootSelector = '[data-secret-reveal-workspace]'
    const panelSelector = '[data-secret-reveal-panel]'
    let pollTimer = null

    const activePanel = (root) => [...root.querySelectorAll(panelSelector)].find((panel) => !panel.hidden) || null

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

    const schedulePolling = (root) => {
        if (pollTimer) window.clearInterval(pollTimer)
        pollTimer = null
        const panel = activePanel(root)
        if (!panel?.querySelector?.('[data-reveal-poll-owner]') && !panel?.matches?.('[data-reveal-poll-owner]')) {
            return
        }
        pollTimer = window.setInterval(() => pollActivePanel(activePanel(root)), 4000)
    }

    const boot = (scope = document) => {
        if (scope.matches?.(rootSelector)) schedulePolling(scope)
        scope.querySelectorAll?.(rootSelector).forEach(schedulePolling)
    }

    window.addEventListener('secret-reveal:tab-changed', () => {
        window.requestAnimationFrame(() => document.querySelectorAll(rootSelector).forEach(schedulePolling))
    })
    document.addEventListener('htmx:load', (event) => boot(event.detail?.elt || document))

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => boot())
    } else {
        boot()
    }
})()
