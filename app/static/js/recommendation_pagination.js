(() => {
    const ROOT_SELECTOR = '[data-kaori-recommendation-pager]'
    const ITEM_SELECTOR = '[data-kaori-recommendation-item]'

    function numberValue(value, fallback) {
        const parsed = Number.parseInt(value, 10)
        return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
    }

    function setButtonState(button, disabled) {
        if (!button) return

        button.disabled = disabled
        button.setAttribute('aria-disabled', disabled ? 'true' : 'false')
        button.classList.toggle('cursor-not-allowed', disabled)
        button.classList.toggle('opacity-70', disabled)
        button.classList.toggle('bg-surface-subtle', disabled)
        button.classList.toggle('text-content-muted', disabled)
        button.classList.toggle('cursor-pointer', !disabled)
        button.classList.toggle('bg-surface-card', !disabled)
        button.classList.toggle('text-content-secondary', !disabled)
    }

    function render(root, requestedPage = null) {
        const items = Array.from(root.querySelectorAll(ITEM_SELECTOR))
        const pageSize = numberValue(root.dataset.pageSize, 5)
        const totalPages = Math.max(1, Math.ceil(items.length / pageSize))
        const storedPage = numberValue(root.dataset.page, 1)
        const page = Math.min(Math.max(requestedPage ?? storedPage, 1), totalPages)
        const startIndex = (page - 1) * pageSize
        const endIndex = Math.min(startIndex + pageSize, items.length)

        root.dataset.page = String(page)

        items.forEach((item, index) => {
            item.hidden = index < startIndex || index >= endIndex
        })

        const controls = root.querySelector('[data-kaori-recommendation-controls]')
        if (!controls) return

        const pageOutput = controls.querySelector('[data-recommendation-page]')
        const pagesOutput = controls.querySelector('[data-recommendation-total-pages]')
        const previous = controls.querySelector('[data-recommendation-previous]')
        const next = controls.querySelector('[data-recommendation-next]')

        if (pageOutput) pageOutput.textContent = String(page)
        if (pagesOutput) pagesOutput.textContent = String(totalPages)

        setButtonState(previous, page <= 1)
        setButtonState(next, page >= totalPages)
    }

    function roots(root = document) {
        const result = []
        if (root instanceof Element && root.matches(ROOT_SELECTOR)) result.push(root)
        if (typeof root.querySelectorAll === 'function') result.push(...root.querySelectorAll(ROOT_SELECTOR))
        return result
    }

    function renderAll(root = document) {
        roots(root).forEach((pager) => render(pager))
        if (window.renderKaoriIcons) window.renderKaoriIcons()
    }

    document.addEventListener('click', (event) => {
        const element = event.target instanceof Element ? event.target : null
        const previous = element?.closest('[data-recommendation-previous]')
        const next = element?.closest('[data-recommendation-next]')
        const button = previous || next
        if (!button || button.disabled) return

        const root = button.closest(ROOT_SELECTOR)
        if (!root) return

        const currentPage = numberValue(root.dataset.page, 1)
        render(root, previous ? currentPage - 1 : currentPage + 1)
        root.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })

    document.addEventListener('DOMContentLoaded', () => renderAll(document))
    document.addEventListener('htmx:afterSwap', (event) => renderAll(event.detail?.target || document))
})()
