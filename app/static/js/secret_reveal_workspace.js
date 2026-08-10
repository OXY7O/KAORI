;(() => {
    const rootSelector = '[data-secret-reveal-workspace]'
    const tabSelector = '[data-secret-reveal-tab]'
    const panelSelector = '[data-secret-reveal-panel]'
    const viewParam = 'reveal_view'
    const deepLinkViews = new Map([
        ['#my-secret-reveal-requests', 'mine'],
        ['#secret-reveal-request-status', 'mine'],
        ['#reveal-session-step-up', 'mine'],
        ['#pending-secret-reveal-approvals', 'approvals'],
    ])
    let pollTimer = null

    const renderIcons = () => {
        window.renderKaoriIcons?.()
        if (!window.renderKaoriIcons && window.lucide) window.lucide.createIcons()
    }

    const viewState = (root) => {
        const tabs = [...root.querySelectorAll(tabSelector)]
        const panels = [...root.querySelectorAll(panelSelector)]
        const tabByKey = new Map(tabs.map((tab) => [tab.dataset.secretRevealTab, tab]).filter(([key]) => Boolean(key)))
        const panelByKey = new Map(
            panels.map((panel) => [panel.dataset.secretRevealPanel, panel]).filter(([key]) => Boolean(key))
        )
        const keys = [...tabByKey.keys()].filter((key) => panelByKey.has(key))
        return { tabs, panels, tabByKey, panelByKey, keys }
    }

    const resolveTabFromLocation = (root) => {
        const state = viewState(root)
        const available = new Set(state.keys)
        const requested = new URL(window.location.href).searchParams.get(viewParam)
        if (requested && available.has(requested)) return requested

        const hashView = deepLinkViews.get(window.location.hash)
        if (hashView && available.has(hashView)) return hashView

        const serverView = root.dataset.secretRevealActiveView
        if (serverView && available.has(serverView)) return serverView

        const serverVisiblePanel = state.panels.find((panel) => !panel.hidden)
        const visibleKey = serverVisiblePanel?.dataset.secretRevealPanel
        if (visibleKey && available.has(visibleKey)) return visibleKey

        return available.has('new') ? 'new' : state.keys[0]
    }

    const syncLocation = (key) => {
        if (!window.history?.replaceState) return
        const url = new URL(window.location.href)
        url.searchParams.set(viewParam, key)
        url.hash = ''
        window.history.replaceState({}, '', url)
    }

    const revealDeepLink = () => {
        const target = window.location.hash ? document.querySelector(window.location.hash) : null
        if (!(target instanceof HTMLElement)) return
        window.requestAnimationFrame(() => target.scrollIntoView({ block: 'start' }))
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
        if (!panel?.querySelector?.('[data-reveal-poll-owner]') && !panel?.matches?.('[data-reveal-poll-owner]')) {
            return
        }
        pollTimer = window.setInterval(() => pollActivePanel(panel), 4000)
    }

    const selectTab = (root, key, focus = false, updateLocation = false) => {
        const state = viewState(root)
        const activeTab = state.tabByKey.get(key)
        const activePanel = state.panelByKey.get(key)

        if (!(activeTab instanceof HTMLElement) || !(activePanel instanceof HTMLElement)) {
            return false
        }

        state.tabs.forEach((tab) => {
            const selected = tab === activeTab
            tab.setAttribute('aria-selected', selected ? 'true' : 'false')
            tab.tabIndex = selected ? 0 : -1
            tab.classList.toggle('border-kaori-primary', selected)
            tab.classList.toggle('text-kaori-primary', selected)
            tab.classList.toggle('border-transparent', !selected)
            tab.classList.toggle('text-content-muted', !selected)
        })

        state.panels.forEach((panel) => {
            panel.toggleAttribute('hidden', panel !== activePanel)
        })

        root.dataset.secretRevealActiveView = key
        schedulePolling(activePanel)
        if (focus) activeTab.focus()
        if (updateLocation) syncLocation(key)
        renderIcons()
        return true
    }

    const tabFromEvent = (root, event) => {
        if (!(event.target instanceof Element)) return null
        const tab = event.target.closest(tabSelector)
        return tab && root.contains(tab) ? tab : null
    }

    const initialise = (root) => {
        if (!(root instanceof HTMLElement) || root.dataset.revealTabsReady === 'true') return
        const initialState = viewState(root)
        if (!initialState.keys.length) return

        root.dataset.revealTabsReady = 'true'
        root.addEventListener('click', (event) => {
            const tab = tabFromEvent(root, event)
            if (!tab) return
            const key = tab.dataset.secretRevealTab
            if (!key) return

            // Only suppress native navigation after the client controller proves
            // that the requested tab/panel pair is complete. Otherwise the real
            // href remains a safe server-rendered fallback instead of a dead tab.
            if (selectTab(root, key, false, true)) event.preventDefault()
        })

        root.addEventListener('keydown', (event) => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
            const tab = tabFromEvent(root, event)
            if (!tab) return
            const state = viewState(root)
            const index = state.tabs.indexOf(tab)
            if (index < 0) return

            event.preventDefault()
            let nextIndex = index
            if (event.key === 'ArrowRight') nextIndex = (index + 1) % state.tabs.length
            if (event.key === 'ArrowLeft') nextIndex = (index - 1 + state.tabs.length) % state.tabs.length
            if (event.key === 'Home') nextIndex = 0
            if (event.key === 'End') nextIndex = state.tabs.length - 1
            const key = state.tabs[nextIndex]?.dataset.secretRevealTab
            if (key) selectTab(root, key, true, true)
        })

        const initialKey = resolveTabFromLocation(root)
        if (initialKey) selectTab(root, initialKey)
        revealDeepLink()
    }

    const boot = (scope = document) => {
        if (scope.matches?.(rootSelector)) initialise(scope)
        scope.querySelectorAll?.(rootSelector).forEach(initialise)
    }

    window.addEventListener('hashchange', () => {
        document.querySelectorAll(rootSelector).forEach((root) => {
            const key = resolveTabFromLocation(root)
            if (key) selectTab(root, key)
            revealDeepLink()
        })
    })
    window.addEventListener('popstate', () => {
        document.querySelectorAll(rootSelector).forEach((root) => {
            const key = resolveTabFromLocation(root)
            if (key) selectTab(root, key)
        })
    })
    document.addEventListener('htmx:load', (event) => boot(event.detail?.elt || document))

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => boot())
    } else {
        boot()
    }
})()
