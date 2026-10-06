;(() => {
    const selector = '[data-protected-value-panel]'
    const timers = new WeakMap()

    const clearValue = (panel, message = 'The one-time Secret value has been removed from the page.') => {
        const timer = timers.get(panel)
        if (timer) window.clearInterval(timer)
        timers.delete(panel)
        const rawValue = panel.querySelector('[data-protected-value]')
        if (rawValue) rawValue.textContent = ''

        const clearedState = document.createElement('div')
        clearedState.className = 'flex items-center gap-3 p-5 text-sm text-content-secondary'

        const icon = document.createElement('i')
        icon.setAttribute('data-lucide', 'eye-off')
        icon.className = 'h-5 w-5'

        const copy = document.createElement('span')
        copy.textContent = message

        clearedState.append(icon, copy)
        panel.replaceChildren(clearedState)
        window.renderKaoriIcons?.()
        if (!window.renderKaoriIcons && window.lucide) window.lucide.createIcons()
    }

    const initialisePanel = (panel) => {
        if (!(panel instanceof HTMLElement) || panel.dataset.protectedValueReady === 'true') return
        panel.dataset.protectedValueReady = 'true'
        let remaining = Number.parseInt(panel.dataset.expiresIn || '0', 10)
        const counter = panel.querySelector('[data-protected-value-countdown]')
        if (!Number.isFinite(remaining) || remaining <= 0) {
            clearValue(panel)
            return
        }
        const interval = window.setInterval(() => {
            remaining -= 1
            if (counter && (remaining % 5 === 0 || remaining <= 5)) counter.textContent = `${Math.max(remaining, 0)}s`
            if (remaining <= 0) clearValue(panel)
        }, 1000)
        timers.set(panel, interval)
    }

    const initialise = (root = document) => {
        if (root.matches?.(selector)) initialisePanel(root)
        root.querySelectorAll?.(selector).forEach(initialisePanel)
    }

    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) return
        document
            .querySelectorAll(selector)
            .forEach((panel) => clearValue(panel, 'The one-time Secret value was cleared when the page became hidden.'))
    })
    window.addEventListener('pagehide', () => document.querySelectorAll(selector).forEach((panel) => clearValue(panel)))
    document.addEventListener('htmx:beforeSwap', (event) => {
        event.detail?.target?.querySelectorAll?.(selector).forEach((panel) => clearValue(panel))
    })
    document.addEventListener('htmx:load', (event) => initialise(event.detail?.elt || document))
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => initialise())
    else initialise()
})()
