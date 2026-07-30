(() => {
    const SELECTOR = '[data-detail-toggle]'
    const inFlight = new Map()

    function refreshIcons() {
        if (window.lucide) window.lucide.createIcons()
    }

    function processHtmx(root) {
        if (window.htmx?.process) window.htmx.process(root)
    }

    function setButtonState(button, open) {
        const label = button.querySelector('[data-detail-toggle-label]')
        const icon = button.querySelector('[data-lucide]')

        button.setAttribute('aria-expanded', open ? 'true' : 'false')
        if (label) label.textContent = open
            ? (button.dataset.detailCloseLabel || 'Hide Details')
            : (button.dataset.detailOpenLabel || 'View More')
        if (icon) icon.setAttribute('data-lucide', open ? 'chevron-up' : 'chevron-down')
    }

    function resolveElements(button) {
        const targetId = button.dataset.detailTarget || ''
        const rowId = button.dataset.detailRow || ''
        return {
            target: targetId ? document.getElementById(targetId) : null,
            row: rowId ? document.getElementById(rowId) : null,
        }
    }

    function cancelRequest(target) {
        const controller = inFlight.get(target.id)
        if (controller) controller.abort()
        inFlight.delete(target.id)
    }

    function closeButton(button) {
        const { target, row } = resolveElements(button)

        if (target) {
            cancelRequest(target)
            if (target.dataset.detailStatic !== 'true') target.innerHTML = ''
            target.dataset.open = 'false'
            target.removeAttribute('aria-busy')
        }
        if (row) row.classList.add('hidden')
        setButtonState(button, false)
    }

    function closeGroup(group, exceptButton = null) {
        document.querySelectorAll(SELECTOR).forEach((button) => {
            if (button !== exceptButton && (button.dataset.detailGroup || 'default') === group) {
                closeButton(button)
            }
        })
    }

    function renderLoading(target) {
        target.setAttribute('aria-busy', 'true')
        target.innerHTML = `
            <div class="flex min-h-24 items-center justify-center gap-2 border-t border-outline-subtle bg-surface-hover px-5 py-5 text-sm font-medium text-content-muted">
                <span class="h-4 w-4 animate-spin rounded-full border-2 border-outline-default border-t-kaori-primary" aria-hidden="true"></span>
                Loading Details
            </div>
        `
    }

    function renderError(target) {
        target.removeAttribute('aria-busy')
        target.innerHTML = `
            <div class="border-t border-critical/30 bg-critical/5 px-5 py-5">
                <p class="text-sm font-semibold text-critical">Unable To Load Details</p>
                <p class="mt-1 text-xs leading-5 text-content-muted">Refresh the inventory data or try opening the detail again.</p>
            </div>
        `
    }

    async function loadDetail(button, target, detailUrl) {
        cancelRequest(target)
        const controller = new AbortController()
        inFlight.set(target.id, controller)

        try {
            const response = await fetch(detailUrl, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'HX-Request': 'true',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                signal: controller.signal,
            })

            if (!response.ok) throw new Error(`Detail request failed with ${response.status}`)
            const html = await response.text()

            if (target.dataset.open !== 'true') return
            target.innerHTML = html
            target.removeAttribute('aria-busy')
            processHtmx(target)
            refreshIcons()
        } catch (error) {
            if (error.name === 'AbortError') return
            renderError(target)
            setButtonState(button, true)
            target.dataset.open = 'true'
        } finally {
            if (inFlight.get(target.id) === controller) inFlight.delete(target.id)
        }
    }

    function openButton(button) {
        const { target, row } = resolveElements(button)
        const detailUrl = button.dataset.detailUrl || ''
        if (!target || !row || !detailUrl) return

        closeGroup(button.dataset.detailGroup || 'default', button)
        row.classList.remove('hidden')
        target.dataset.open = 'true'
        setButtonState(button, true)
        renderLoading(target)
        refreshIcons()
        loadDetail(button, target, detailUrl)
    }

    document.addEventListener('click', (event) => {
        const element = event.target instanceof Element ? event.target : null
        const button = element?.closest(SELECTOR)
        if (!button) return

        event.preventDefault()
        const { target, row } = resolveElements(button)
        if (!target || !row) return

        if (target.dataset.open === 'true') {
            closeButton(button)
            refreshIcons()
            return
        }

        openButton(button)
    })
})()
