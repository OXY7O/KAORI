;(() => {
    const PAGE_ID = 'analytics-overview-page'
    const TRACKER_ID = 'analytics-overview-load-tracker'
    const SECTION_SELECTOR = '[data-overview-lazy-section="true"]'
    const REQUESTED_STATES = new Set(['loading', 'loaded', 'failed'])

    function overviewPage() {
        return document.getElementById(PAGE_ID)
    }

    function trackerElement() {
        return document.getElementById(TRACKER_ID)
    }

    function lazySections() {
        const page = overviewPage()
        return page ? Array.from(page.querySelectorAll(SECTION_SELECTOR)) : []
    }

    function requestElement(event) {
        return event.detail?.elt || event.detail?.target || event.target
    }

    function trackedSection(event) {
        const element = requestElement(event)
        return element?.closest?.(SECTION_SELECTOR) || null
    }

    function isOverviewRefresh(event) {
        const element = requestElement(event)
        return Boolean(element?.closest?.('[data-overview-refresh-request="true"]'))
    }

    function showTracker(mode = 'loading') {
        const tracker = trackerElement()
        if (!tracker) return
        tracker.classList.remove('hidden')
        tracker.dataset.overviewLoadState = mode
    }

    function hideTracker() {
        const tracker = trackerElement()
        if (!tracker) return
        tracker.classList.add('hidden')
        tracker.dataset.overviewLoadState = 'idle'
    }

    function updateTracker() {
        const tracker = trackerElement()
        if (!tracker) return

        const requested = lazySections().filter((section) => REQUESTED_STATES.has(section.dataset.overviewLoadState))
        if (!requested.length) {
            hideTracker()
            return
        }

        const completed = requested.filter((section) =>
            ['loaded', 'failed'].includes(section.dataset.overviewLoadState)
        ).length
        const failed = requested.filter((section) => section.dataset.overviewLoadState === 'failed').length
        const total = requested.length
        const percentage = Math.max(4, Math.round((completed / total) * 100))
        const title = tracker.querySelector('[data-overview-load-title]')
        const description = tracker.querySelector('[data-overview-load-description]')
        const counter = tracker.querySelector('[data-overview-load-counter]')
        const progress = tracker.querySelector('[data-overview-load-progress]')

        if (counter) counter.textContent = `${completed}/${total} Requested Sections`
        if (progress) progress.style.width = `${percentage}%`

        if (completed >= total) {
            tracker.dataset.overviewLoadState = failed ? 'completed-with-errors' : 'complete'
            if (title)
                title.textContent = failed ? 'Analytics Section Loaded With Exceptions' : 'Analytics Section Ready'
            if (description) {
                description.textContent = failed
                    ? `${failed} requested section${failed === 1 ? '' : 's'} could not be refreshed.`
                    : 'The requested committed snapshot section is available.'
            }
            window.setTimeout(
                () => {
                    const current = trackerElement()
                    if (current && ['complete', 'completed-with-errors'].includes(current.dataset.overviewLoadState)) {
                        current.classList.add('hidden')
                    }
                },
                failed ? 2600 : 1000
            )
            return
        }

        showTracker('loading')
        if (title) title.textContent = 'Loading Analytics Section'
        if (description) description.textContent = 'Reading the requested committed analytics snapshot.'
    }

    function initializeTracker() {
        const tracker = trackerElement()
        if (!tracker) return

        lazySections().forEach((section) => {
            if (!section.dataset.overviewLoadState) section.dataset.overviewLoadState = 'idle'
        })
        updateTracker()
    }

    function markFailed(event) {
        const section = trackedSection(event)
        if (!section) return
        section.dataset.overviewLoadState = 'failed'
        updateTracker()
    }

    window.kaoriInitializeOverviewLoadTracker = initializeTracker

    document.body.addEventListener('htmx:beforeRequest', (event) => {
        const section = trackedSection(event)
        if (section) {
            section.dataset.overviewLoadState = 'loading'
            showTracker('loading')
            updateTracker()
            return
        }

        if (!isOverviewRefresh(event)) return
        const tracker = trackerElement()
        showTracker('refreshing')
        if (!tracker) return
        const title = tracker.querySelector('[data-overview-load-title]')
        const description = tracker.querySelector('[data-overview-load-description]')
        if (title) title.textContent = 'Refreshing Analytics Overview'
        if (description) description.textContent = 'Applying the selected cluster and analysis window.'
    })

    document.body.addEventListener('htmx:afterSettle', (event) => {
        const section = trackedSection(event)
        if (section && section.dataset.overviewLoadState !== 'failed') {
            section.dataset.overviewLoadState = 'loaded'
            updateTracker()
        }

        const target = event.detail?.target || event.target
        if (target?.id === PAGE_ID) window.setTimeout(initializeTracker, 0)
    })
    ;['htmx:responseError', 'htmx:sendError', 'htmx:timeout'].forEach((eventName) => {
        document.body.addEventListener(eventName, markFailed)
    })

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeTracker, { once: true })
    } else {
        initializeTracker()
    }
})()
