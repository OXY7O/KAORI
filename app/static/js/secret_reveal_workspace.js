;(() => {
    const rootSelector = '[data-secret-reveal-workspace]'
    const panelSelector = '[data-secret-reveal-panel]'
    const stepUpTriggerSelector = '[data-reveal-step-up-trigger]'
    const submittedNavigationKey = 'kaori:secret-reveal:request-navigation'
    const approvedRequestsTriggerSelector = '[data-reveal-approved-requests-trigger]'
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

    // Keep navigation inside the KAORI main scroll surface. Avoid scrolling
    // visible Step-Up content: browser-wide scrollIntoView can displace the
    // nested application shell and expose a blank strip below the workspace.
    const showWithinMainScroll = (target) => {
        const main = target.closest('[data-kaori-main-scroll]')
        const bounds = target.getBoundingClientRect()
        const viewport = main?.getBoundingClientRect() || { top: 0, bottom: window.innerHeight }
        const padding = 20

        if (bounds.top >= viewport.top + padding && bounds.bottom <= viewport.bottom - padding) return

        if (main) {
            const limit = Math.max(0, main.scrollHeight - main.clientHeight)
            const next = Math.max(0, Math.min(limit, main.scrollTop + bounds.top - viewport.top - padding))
            if (Math.abs(main.scrollTop - next) < 1) return
            main.scrollTo({ top: next, behavior: 'auto' })
        } else {
            target.scrollIntoView({ behavior: 'auto', block: 'nearest' })
        }
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

        showWithinMainScroll(target)
        const password = target.querySelector('[data-reveal-step-up-password]')
        const focusTarget = password && !password.disabled ? password : target
        focusTarget.focus({ preventScroll: true })
    }

    // The verified-session CTA must not use the browser's native hash scroll:
    // the table can be taller than the viewport, and native anchoring may move
    // the surrounding shell. Focus a row-sized action within KAORI's main scroller.
    const navigateToApprovedRequest = (event) => {
        if (!(event.target instanceof Element) || event.defaultPrevented || event.button !== 0) return
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return

        const link = event.target.closest(approvedRequestsTriggerSelector)
        if (!link) return

        const workspace = link.closest(rootSelector)
        const panel = workspace?.querySelector('[data-secret-reveal-panel="mine"]')
        if (!panel || panel.hidden) return

        // Prefer a short, focusable action over the full-height registry card.
        // If the currently filtered page has no approved row, show its header.
        const target =
            panel.querySelector('[data-reveal-once-action]') || panel.querySelector('#my-secret-reveal-requests')
        if (!target) return

        event.preventDefault()
        const url = new URL(window.location.href)
        url.searchParams.set('reveal_view', 'mine')
        url.hash = 'my-secret-reveal-requests'
        window.history.replaceState(window.history.state, '', url)

        showWithinMainScroll(target)
        target.focus({ preventScroll: true })
    }

    // Reveal responses are ephemeral; guide the operator to the protected
    // result in My Requests without moving Secret bytes into toast/history.
    const focusRevealResult = (event) => {
        const result = event.detail?.target
        if (result?.id !== 'reveal-value-output') return
        if (!result.firstElementChild) return
        showWithinMainScroll(result)
        result.focus({ preventScroll: true })
    }

    // The request form performs a full POST/redirect. Mark navigation only,
    // never form fields or Secret material, so the redirected workspace does
    // not restore the previous long New Request scroll position.
    const markRequestNavigation = (event) => {
        if (!(event.target instanceof HTMLFormElement)) return
        if (!event.target.matches('[data-reveal-request-submit-form]')) return
        try {
            window.sessionStorage.setItem(submittedNavigationKey, 'mine')
        } catch (_) {
            // Storage-disabled browsers continue with normal server POST.
        }
    }

    const restoreSubmittedWorkspacePosition = () => {
        let targetView = null
        try {
            targetView = window.sessionStorage.getItem(submittedNavigationKey)
            window.sessionStorage.removeItem(submittedNavigationKey)
        } catch (_) {
            return
        }
        if (targetView !== 'mine') return
        const view = new URL(window.location.href).searchParams.get('reveal_view')
        if (view !== 'mine') return
        // Await the Alpine-selected tab and the browser's own scroll restore.
        window.requestAnimationFrame(() =>
            window.requestAnimationFrame(() => {
                const main = document.querySelector('[data-kaori-main-scroll]')
                main?.scrollTo({ top: 0, behavior: 'auto' })
            })
        )
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
    document.addEventListener('click', navigateToApprovedRequest)
    document.addEventListener('submit', markRequestNavigation)
    document.addEventListener('htmx:afterSwap', focusRevealResult)
    document.addEventListener('htmx:load', (event) => boot(event.detail?.elt || document))

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            boot()
            restoreSubmittedWorkspacePosition()
        })
    } else {
        boot()
        restoreSubmittedWorkspacePosition()
    }
})()
