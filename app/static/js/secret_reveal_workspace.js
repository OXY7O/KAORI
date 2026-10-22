;(() => {
    const rootSelector = '[data-secret-reveal-workspace]'
    const panelSelector = '[data-secret-reveal-panel]'
    const stepUpTriggerSelector = '[data-reveal-step-up-trigger]'
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
        // Do not discard an in-progress approval decision form during the
        // regular read-only poll. Resume automatically after the editor closes.
        if (owner.querySelector?.('[data-approval-decision-editor][data-open="true"]')) return
        window.htmx.ajax('GET', url, { target, swap: 'outerHTML' })
    }

    // Delegate the action so it survives HTMX polling and table replacement.
    // A real URL remains on the link for non-JavaScript / failed-load fallback.
    const navigateToStepUp = (event) => {
        if (!(event.target instanceof Element) || event.defaultPrevented || event.button !== 0) return
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return

        const link = event.target.closest(stepUpTriggerSelector)
        if (!link) return

        const workspace = link.closest(rootSelector)
        const target = workspace?.querySelector('#reveal-session-step-up')
        const panel = target?.closest(panelSelector)
        if (!target || !panel || panel.hidden) return

        event.preventDefault()
        const url = new URL(window.location.href)
        url.searchParams.set('reveal_view', 'mine')
        url.hash = 'reveal-session-step-up'
        window.history.replaceState(window.history.state, '', url)

        const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true
        target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
        const password = target.querySelector('[data-reveal-step-up-password]')
        const focusTarget = password && !password.disabled ? password : target
        focusTarget.focus({ preventScroll: true })
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
    document.addEventListener('click', navigateToStepUp)
    document.addEventListener('htmx:load', (event) => boot(event.detail?.elt || document))

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => boot())
    } else {
        boot()
    }
})()
