(() => {
    const SELECTOR = '[data-detail-toggle]'

    function setButtonState(button, open) {
        const label = button.querySelector('[data-detail-toggle-label]')
        const icon = button.querySelector('[data-lucide]')

        button.setAttribute('aria-expanded', open ? 'true' : 'false')
        if (label) label.textContent = open ? 'Hide Details' : 'View More'
        if (icon) icon.setAttribute('data-lucide', open ? 'chevron-up' : 'chevron-down')
    }

    function closeButton(button) {
        const targetId = button.dataset.detailTarget
        const rowId = button.dataset.detailRow
        const target = targetId ? document.getElementById(targetId) : null
        const row = rowId ? document.getElementById(rowId) : null

        if (target) {
            target.innerHTML = ''
            target.dataset.open = 'false'
        }
        if (row) row.classList.add('hidden')
        setButtonState(button, false)
    }

    function closeGroup(group, exceptButton = null) {
        document.querySelectorAll(`${SELECTOR}[data-detail-group="${CSS.escape(group)}"]`).forEach((button) => {
            if (button !== exceptButton) closeButton(button)
        })
    }

    document.addEventListener('click', (event) => {
        const element = event.target instanceof Element ? event.target : null
        const button = element?.closest(SELECTOR)
        if (!button) return

        const target = document.getElementById(button.dataset.detailTarget || '')
        const row = document.getElementById(button.dataset.detailRow || '')
        if (!target || !row) return

        if (target.dataset.open === 'true') {
            event.preventDefault()
            event.stopImmediatePropagation()
            closeButton(button)
            if (window.lucide) window.lucide.createIcons()
            return
        }

        closeGroup(button.dataset.detailGroup || 'default', button)
        row.classList.remove('hidden')
        target.dataset.open = 'true'
        setButtonState(button, true)
        if (window.lucide) window.lucide.createIcons()
    }, true)

    document.addEventListener('htmx:afterSwap', (event) => {
        if (event.target?.matches?.('[data-detail-content]') && window.lucide) {
            window.lucide.createIcons()
        }
    })

    document.addEventListener('htmx:responseError', (event) => {
        const target = event.detail?.target
        if (!target?.matches?.('[data-detail-content]')) return
        const button = document.querySelector(`${SELECTOR}[data-detail-target="${CSS.escape(target.id)}"]`)
        if (button) closeButton(button)
    })
})()
