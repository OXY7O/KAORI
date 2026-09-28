;(() => {
    let opener = null
    const focusableSelector = [
        'button:not([disabled])',
        '[href]',
        'input:not([disabled])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])',
    ].join(',')

    const visibleModal = () => document.querySelector('[data-tenant-adoption-modal]:not(.hidden)')

    const openModal = (button) => {
        const id = button.dataset.tenantAdoptionModalId || ''
        const modal = document.getElementById(id)
        if (!(modal instanceof HTMLElement)) return

        opener = button
        modal.classList.remove('hidden')
        modal.classList.add('flex')
        modal.setAttribute('aria-hidden', 'false')
        document.documentElement.classList.add('overflow-hidden')

        const dialog = modal.querySelector('[role="dialog"]')
        const firstFocusable = dialog?.querySelector(focusableSelector)
        ;(firstFocusable || dialog)?.focus()
    }

    const closeModal = (modal) => {
        if (!(modal instanceof HTMLElement)) return
        modal.classList.add('hidden')
        modal.classList.remove('flex')
        modal.setAttribute('aria-hidden', 'true')
        document.documentElement.classList.remove('overflow-hidden')
        opener?.focus()
        opener = null
    }

    document.addEventListener('click', (event) => {
        const open = event.target.closest('[data-tenant-adoption-open]')
        if (open) {
            event.preventDefault()
            if (!open.disabled) openModal(open)
            return
        }

        const close = event.target.closest('[data-tenant-adoption-close]')
        if (close) closeModal(close.closest('[data-tenant-adoption-modal]'))
    })

    document.addEventListener('htmx:afterRequest', (event) => {
        const form = event.target instanceof HTMLFormElement ? event.target : event.target?.closest?.('form')
        if (!(form instanceof HTMLFormElement)) return
        const modal = form.closest('[data-tenant-adoption-modal]')
        if (modal) closeModal(modal)
    })

    document.addEventListener('keydown', (event) => {
        const modal = visibleModal()
        if (!modal) return

        if (event.key === 'Escape') {
            event.preventDefault()
            closeModal(modal)
            return
        }
        if (event.key !== 'Tab') return

        const dialog = modal.querySelector('[role="dialog"]')
        const focusable = [...(dialog?.querySelectorAll(focusableSelector) || [])].filter(
            (element) => element instanceof HTMLElement && element.offsetParent !== null
        )
        if (!focusable.length) {
            event.preventDefault()
            dialog?.focus()
            return
        }

        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault()
            last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault()
            first.focus()
        }
    })
})()
