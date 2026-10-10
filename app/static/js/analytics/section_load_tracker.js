;(() => {
    // Counts requested committed-evidence HTMX fragments, never Celery/JobExecution progress.
    const ROOT = '[data-analytics-section-tracker-root]'
    const TRACKER = '[data-analytics-section-load-tracker]'
    const SECTION = '[data-analytics-lazy-section="true"], [data-overview-lazy-section="true"]'
    const REQUESTED = new Set(['loading', 'loaded', 'failed'])

    const roots = () => Array.from(document.querySelectorAll(ROOT))
    const tracker = (root) => root?.querySelector(TRACKER)
    const sections = (root) => Array.from(root?.querySelectorAll(SECTION) || [])
    const state = (el) => el.dataset.analyticsLoadState || el.dataset.overviewLoadState || 'idle'

    function setState(el, value) {
        el.dataset.analyticsLoadState = value
        el.dataset.overviewLoadState = value
    }
    function setText(el, selector, value) {
        const target = el?.querySelector(selector)
        if (target) target.textContent = value
    }
    function hide(view) {
        if (!view) return
        view.classList.add('hidden')
        view.dataset.overviewLoadState = 'idle'
    }
    function show(view, mode) {
        if (!view) return
        view.classList.remove('hidden')
        view.dataset.overviewLoadState = mode
    }
    function update(root) {
        const view = tracker(root)
        if (!view) return
        const requested = sections(root).filter((node) => REQUESTED.has(state(node)))
        if (!requested.length) {
            hide(view)
            return
        }
        const complete = requested.filter((node) => state(node) === 'loaded' || state(node) === 'failed').length
        const failed = requested.filter((node) => state(node) === 'failed').length
        const total = requested.length
        setText(view, '[data-analytics-load-counter]', complete + '/' + total + ' Requested Sections')
        const progress = view.querySelector('[data-analytics-load-progress]')
        if (progress) progress.style.width = Math.max(4, Math.round((complete / total) * 100)) + '%'
        if (complete !== total) {
            setText(view, '[data-analytics-load-title]', root.dataset.analyticsLoadTitle || 'Loading Analytics Section')
            setText(view, '[data-analytics-load-description]', root.dataset.analyticsLoadDescription || 'Reading the requested committed analytics snapshot.')
            show(view, 'loading')
            return
        }
        const mode = failed ? 'completed-with-errors' : 'complete'
        setText(view, '[data-analytics-load-title]', failed ? 'Analytics Section Loaded With Exceptions' : 'Analytics Section Ready')
        setText(view, '[data-analytics-load-description]', failed ? failed + ' requested section(s) could not be refreshed.' : 'The requested committed snapshot section is available.')
        show(view, mode)
        window.setTimeout(() => {
            if (view.isConnected && view.dataset.overviewLoadState === mode) hide(view)
        }, failed ? 2600 : 1000)
    }
    function requestElement(event) {
        return event.detail?.elt || event.detail?.target || event.target
    }
    function trackedSection(event) {
        return requestElement(event)?.closest?.(SECTION) || null
    }
    function currentSection(section) {
        if (!section?.id) return section
        const replacement = document.getElementById(section.id)
        return replacement?.matches?.(SECTION) ? replacement : section
    }
    function initialize() {
        roots().forEach((root) => {
            sections(root).forEach((node) => {
                if (!node.dataset.analyticsLoadState && !node.dataset.overviewLoadState) setState(node, 'idle')
            })
            update(root)
        })
    }

    // Compatibility hook for Kubernetes Overview callers.
    window.kaoriInitializeOverviewLoadTracker = initialize
    document.body.addEventListener('htmx:beforeRequest', (event) => {
        const section = trackedSection(event)
        const root = section?.closest(ROOT)
        if (section && root) {
            setState(section, 'loading')
            update(root)
            return
        }
        const refresh = requestElement(event)?.closest?.('[data-analytics-refresh-request="true"], [data-overview-refresh-request="true"]')
        const refreshRoot = refresh?.closest(ROOT)
        if (!refreshRoot) return
        const view = tracker(refreshRoot)
        show(view, 'refreshing')
        setText(view, '[data-analytics-load-counter]', 'Applying Filter')
        const progress = view?.querySelector('[data-analytics-load-progress]')
        if (progress) progress.style.width = '4%'
        setText(view, '[data-analytics-load-title]', refreshRoot.dataset.analyticsRefreshTitle || 'Refreshing Analytics Overview')
        setText(view, '[data-analytics-load-description]', refreshRoot.dataset.analyticsRefreshDescription || 'Applying the selected analytics scope and time range.')
    })
    document.body.addEventListener('htmx:afterSettle', (event) => {
        const section = currentSection(trackedSection(event))
        const root = section?.closest?.(ROOT)
        if (root) {
            if (state(section) !== 'failed') setState(section, 'loaded')
            update(root)
        }
        const target = event.detail?.target || event.target
        if (target?.matches?.(ROOT)) window.setTimeout(initialize, 0)
    })
    ;['htmx:responseError', 'htmx:sendError', 'htmx:timeout'].forEach((eventName) => {
        document.body.addEventListener(eventName, (event) => {
            const section = currentSection(trackedSection(event))
            const root = section?.closest?.(ROOT)
            if (root) {
                setState(section, 'failed')
                update(root)
                return
            }
            const refresh = requestElement(event)?.closest?.(
                '[data-analytics-refresh-request="true"], [data-overview-refresh-request="true"]'
            )
            const refreshRoot = refresh?.closest?.(ROOT)
            const view = tracker(refreshRoot)
            if (!view) return
            setText(view, '[data-analytics-load-title]', 'Analytics Refresh Failed')
            setText(view, '[data-analytics-load-description]', 'The requested analytics scope could not be refreshed.')
            setText(view, '[data-analytics-load-counter]', 'Refresh Failed')
            show(view, 'completed-with-errors')
            window.setTimeout(() => {
                if (view.isConnected && view.dataset.overviewLoadState === 'completed-with-errors') hide(view)
            }, 2600)
        })
    })
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, { once: true })
    } else {
        initialize()
    }
})()
