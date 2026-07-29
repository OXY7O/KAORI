(() => {
    const SELECTOR = '[data-detail-toggle]'

    function refreshIcons() {
        if (window.lucide) window.lucide.createIcons()
    }

    function setButtonState(button, open) {
        const label = button.querySelector('[data-detail-toggle-label]')
        const icon = button.querySelector('[data-lucide]')

        button.setAttribute('aria-expanded', open ? 'true' : 'false')
        if (label) label.textContent = open ? 'Hide Details' : 'View More'
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

    function closeButton(button) {
        const { target, row } = resolveElements(button)

        if (target) {
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

    function openButton(button) {
        const { target, row } = resolveElements(button)
        const detailUrl = button.dataset.detailUrl || button.getAttribute('hx-get') || ''
        if (!target || !row || !detailUrl || !window.htmx) return

        closeGroup(button.dataset.detailGroup || 'default', button)
        row.classList.remove('hidden')
        target.dataset.open = 'true'
        setButtonState(button, true)
        renderLoading(target)
        refreshIcons()

        window.htmx.ajax('GET', detailUrl, {
            target: `#${CSS.escape(target.id)}`,
            swap: 'innerHTML',
        })
    }

    document.addEventListener('click', (event) => {
        const element = event.target instanceof Element ? event.target : null
        const button = element?.closest(SELECTOR)
        if (!button) return

        event.preventDefault()
        event.stopImmediatePropagation()

        const { target, row } = resolveElements(button)
        if (!target || !row) return

        if (target.dataset.open === 'true') {
            closeButton(button)
            refreshIcons()
            return
        }

        openButton(button)
    }, true)

    document.addEventListener('htmx:afterSwap', (event) => {
        const target = event.target
        if (!target?.matches?.('[data-detail-content]')) return
        target.removeAttribute('aria-busy')
        target.dataset.open = 'true'
        refreshIcons()
    })

    document.addEventListener('htmx:responseError', (event) => {
        const target = event.detail?.target
        if (!target?.matches?.('[data-detail-content]')) return
        const button = document.querySelector(`${SELECTOR}[data-detail-target="${CSS.escape(target.id)}"]`)
        if (button) closeButton(button)
    })
})()
