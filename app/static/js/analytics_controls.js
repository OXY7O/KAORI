;(() => {
    const clampPercent = (value) => Math.max(0, Math.min(Number(value) || 0, 100))

    const ANALYTICS_TAB_ACTIVE_CLASSES = ['border-kaori-primary', 'bg-kaori-soft', 'text-kaori-primary']
    const ANALYTICS_TAB_INACTIVE_CLASSES = [
        'border-transparent',
        'bg-surface-card',
        'text-content-secondary',
        'hover:border-outline-default',
        'hover:bg-surface-card',
        'hover:text-content-primary',
    ]

    function analyticsTabStorageKey(tabsetId = 'default') {
        return `kaori:analytics-tab:${window.location.pathname}:${tabsetId}`
    }

    function requestedAnalyticsTab(allowedTabs, defaultTab, tabsetId = 'default') {
        const requestedTab = new URL(window.location.href).searchParams.get('tab')
        if (allowedTabs.includes(requestedTab)) return requestedTab

        try {
            const storedTab = window.sessionStorage.getItem(analyticsTabStorageKey(tabsetId))
            if (allowedTabs.includes(storedTab)) return storedTab
        } catch {
            // Storage can be unavailable in hardened browser modes.
        }

        return defaultTab
    }

    function analyticsTabButtons(tabset) {
        return Array.from(tabset.querySelectorAll('[data-analytics-tab-button]')).filter(
            (button) => button.closest('[data-analytics-tabset]') === tabset
        )
    }

    function analyticsTabPanels(tabset) {
        return Array.from(tabset.querySelectorAll('[data-analytics-tab-panel]')).filter(
            (panel) => panel.closest('[data-analytics-tabset]') === tabset
        )
    }

    function notifyAnalyticsTabVisible(panel, tabId, tabsetId) {
        if (!panel) return

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (!panel.isConnected || panel.hidden) return
                panel.dispatchEvent(
                    new CustomEvent('kaori:analytics-tab-visible', {
                        bubbles: true,
                        detail: { tabId, tabsetId },
                    })
                )
                window.dispatchEvent(new Event('resize'))
            })
        })
    }

    function setAnalyticsTab(tabset, tabId, { persist = true, focus = false } = {}) {
        if (!tabset?.isConnected || !tabId) return false

        const buttons = analyticsTabButtons(tabset)
        const allowedTabs = buttons.map((button) => button.dataset.analyticsTabButton).filter(Boolean)
        if (!allowedTabs.includes(tabId)) return false

        const alpineState = tabset._x_dataStack?.[0]
        if (alpineState && alpineState.activeTab !== tabId) {
            alpineState.activeTab = tabId
        }

        buttons.forEach((button) => {
            const selected = button.dataset.analyticsTabButton === tabId
            button.setAttribute('aria-selected', selected ? 'true' : 'false')
            button.tabIndex = selected ? 0 : -1
            button.classList.remove(...ANALYTICS_TAB_ACTIVE_CLASSES, ...ANALYTICS_TAB_INACTIVE_CLASSES)
            button.classList.add(...(selected ? ANALYTICS_TAB_ACTIVE_CLASSES : ANALYTICS_TAB_INACTIVE_CLASSES))
            if (selected && focus) button.focus({ preventScroll: true })
        })

        analyticsTabPanels(tabset).forEach((panel) => {
            panel.hidden = panel.dataset.analyticsTabPanel !== tabId
        })

        if (tabset.dataset.analyticsUpdateQuery !== 'false') {
            const pageRoot = tabset.closest('[id$="-page"]') || document
            pageRoot.querySelectorAll('[data-analytics-preserve-tab] input[name="tab"]').forEach((field) => {
                field.value = tabId
            })
        }

        const tabsetId = tabset.dataset.analyticsTabsetId || tabset.id || 'default'
        if (persist) {
            try {
                window.sessionStorage.setItem(analyticsTabStorageKey(tabsetId), tabId)
            } catch {
                // Native DOM state still keeps the current tab active.
            }
        }

        const activePanel = analyticsTabPanels(tabset).find((panel) => panel.dataset.analyticsTabPanel === tabId)
        if (activePanel) {
            const activationTargets = [
                ...(activePanel.matches?.('[hx-trigger*="kaori:analytics-tab-activated"]') ? [activePanel] : []),
                ...activePanel.querySelectorAll('[hx-trigger*="kaori:analytics-tab-activated"]'),
            ]
            activationTargets.forEach((target) => {
                if (window.htmx?.trigger) {
                    window.htmx.trigger(target, 'kaori:analytics-tab-activated')
                } else {
                    target.dispatchEvent(new CustomEvent('kaori:analytics-tab-activated', { bubbles: true }))
                }
            })
            notifyAnalyticsTabVisible(activePanel, tabId, tabsetId)
        }
        if (window.renderKaoriIcons) window.renderKaoriIcons()
        return true
    }

    window.kaoriAnalyticsTabs = (defaultTab, allowedTabs, tabsetId = 'default') => {
        const tabs = Array.isArray(allowedTabs) ? allowedTabs : []

        return {
            activeTab: requestedAnalyticsTab(tabs, defaultTab, tabsetId),
            setTab(tab) {
                if (!tabs.includes(tab)) return
                this.activeTab = tab
            },
        }
    }

    function hydrateProgressBars(root = document) {
        root.querySelectorAll('.kaori-progress-fill[data-progress]').forEach((element) => {
            element.style.width = `${clampPercent(element.dataset.progress)}%`
        })
    }

    function hydrateProgressRings(root = document) {
        root.querySelectorAll('[data-progress-ring]').forEach((element) => {
            const value = clampPercent(element.dataset.progressRing)
            element.setAttribute('stroke-dasharray', `${value} 100`)
        })
    }

    function resetDependentFields(control) {
        const form = control.form
        const specification = control.dataset.kaoriResetFields

        if (!form || !specification) return

        for (const entry of specification.split(',')) {
            const [rawName, ...rawValue] = entry.split('=')
            const name = rawName.trim()
            if (!name) continue

            const field = form.elements.namedItem(name)
            if (!field || (typeof RadioNodeList !== 'undefined' && field instanceof RadioNodeList)) continue

            field.value = rawValue.join('=').trim()
        }
    }

    function stabilizeAlertsAfterSwap(root) {
        const candidate = root || document
        const connectedCandidate = candidate.isConnected ? candidate : document
        const alertsRoot =
            connectedCandidate?.id === 'alerts-page-content'
                ? connectedCandidate
                : connectedCandidate?.querySelector?.('#alerts-page-content') ||
                  document.querySelector('#alerts-page-content')
        if (!alertsRoot?.isConnected) return

        window.dispatchEvent(new CustomEvent('kaori:alerts-collapse'))

        const tabset = alertsRoot.querySelector('[data-alerts-tabset]')
        if (tabset && window.Alpine && !tabset._x_dataStack) {
            window.Alpine.initTree(tabset)
        }
    }

    function stabilizeAnalyticsExpandables(root) {
        const candidate = root || document
        const connectedCandidate = candidate.isConnected ? candidate : document
        const expandableRoots = []

        if (connectedCandidate?.matches?.('[x-data]')) expandableRoots.push(connectedCandidate)
        connectedCandidate?.querySelectorAll?.('[x-data]').forEach((element) => expandableRoots.push(element))

        if (window.Alpine) {
            expandableRoots.forEach((element) => {
                if (element.isConnected && !element._x_dataStack) window.Alpine.initTree(element)
            })
        }

        window.dispatchEvent(new CustomEvent('kaori:analytics-collapse-details'))
    }

    function stabilizeAnalyticsTabsets(root) {
        const candidate = root || document
        const connectedCandidate = candidate.isConnected ? candidate : document
        const tabsets = []

        if (connectedCandidate?.matches?.('[data-analytics-tabset]')) {
            tabsets.push(connectedCandidate)
        }
        connectedCandidate?.querySelectorAll?.('[data-analytics-tabset]').forEach((tabset) => tabsets.push(tabset))

        tabsets.forEach((tabset) => {
            if (!tabset?.isConnected) return

            if (window.Alpine && !tabset._x_dataStack) {
                window.Alpine.initTree(tabset)
            }

            const buttons = analyticsTabButtons(tabset)
            const allowedTabs = buttons.map((button) => button.dataset.analyticsTabButton).filter(Boolean)
            const tabsetId = tabset.dataset.analyticsTabsetId || tabset.id || 'default'
            const alpineTab = tabset._x_dataStack?.[0]?.activeTab
            const activeTab = allowedTabs.includes(alpineTab)
                ? alpineTab
                : requestedAnalyticsTab(allowedTabs, tabset.dataset.defaultTab, tabsetId)

            setAnalyticsTab(tabset, activeTab, { persist: false })
        })
    }

    function hydrateAnalyticsUi(root = document) {
        hydrateProgressBars(root)
        hydrateProgressRings(root)

        if (window.renderKaoriIcons) {
            window.renderKaoriIcons()
        } else if (window.lucide) {
            window.lucide.createIcons()
        }
    }

    document.addEventListener(
        'change',
        (event) => {
            const control = event.target.closest('[data-kaori-reset-fields]')
            if (control) resetDependentFields(control)
        },
        true
    )

    document.addEventListener(
        'click',
        (event) => {
            const button = event.target.closest?.('[data-analytics-tab-button]')
            if (!button) return

            const tabset = button.closest('[data-analytics-tabset]')
            if (!tabset) return

            event.preventDefault()
            setAnalyticsTab(tabset, button.dataset.analyticsTabButton)
        },
        true
    )

    document.addEventListener(
        'keydown',
        (event) => {
            const button = event.target.closest?.('[data-analytics-tab-button]')
            if (!button || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return

            const tabset = button.closest('[data-analytics-tabset]')
            if (!tabset) return

            const buttons = analyticsTabButtons(tabset)
            const currentIndex = buttons.indexOf(button)
            if (currentIndex < 0) return

            event.preventDefault()
            let nextIndex = currentIndex
            if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % buttons.length
            if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + buttons.length) % buttons.length
            if (event.key === 'Home') nextIndex = 0
            if (event.key === 'End') nextIndex = buttons.length - 1

            const nextButton = buttons[nextIndex]
            setAnalyticsTab(tabset, nextButton.dataset.analyticsTabButton, { focus: true })
        },
        true
    )

    document.addEventListener('DOMContentLoaded', () => {
        hydrateAnalyticsUi()
        stabilizeAnalyticsExpandables(document)
        stabilizeAnalyticsTabsets(document)
    })
    document.body.addEventListener('htmx:load', (event) => hydrateAnalyticsUi(event.detail.elt || document))
    document.body.addEventListener('htmx:afterSwap', (event) => {
        const root = event.detail.target || document
        hydrateAnalyticsUi(root)
        stabilizeAnalyticsExpandables(root)
        stabilizeAlertsAfterSwap(root)
        stabilizeAnalyticsTabsets(root)
    })
    document.body.addEventListener('htmx:afterSettle', (event) => {
        const root = event.detail.elt || document
        hydrateAnalyticsUi(root)
        stabilizeAnalyticsExpandables(root)
        stabilizeAnalyticsTabsets(root)
    })
})()
