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

    // Adoption and Namespace attachment share a route, but not a Tenant identity
    // contract. Keep the create-only controls out of the submitted form in attach mode.
    const syncAdoptionDestination = (modal) => {
        if (!(modal instanceof HTMLElement)) return
        const destination = modal.querySelector('[data-tenant-adoption-destination]')
        if (!(destination instanceof HTMLSelectElement)) return

        const isAttachment = Boolean(destination.value.trim())
        const createFields = modal.querySelector('[data-tenant-adoption-create-fields]')
        const attachFields = modal.querySelector('[data-tenant-adoption-attach-fields]')
        const selected = destination.selectedOptions[0]

        for (const element of modal.querySelectorAll('[data-tenant-adoption-create-copy]')) {
            element.classList.toggle('hidden', isAttachment)
        }
        for (const element of modal.querySelectorAll('[data-tenant-adoption-attach-copy]')) {
            element.classList.toggle('hidden', !isAttachment)
        }
        if (createFields instanceof HTMLElement) {
            createFields.classList.toggle('hidden', isAttachment)
            for (const field of createFields.querySelectorAll('[name="tenant_name"], [name="environment"]')) {
                if (!(field instanceof HTMLInputElement || field instanceof HTMLSelectElement)) continue
                field.disabled = isAttachment
                field.required = !isAttachment
            }
        }
        if (attachFields instanceof HTMLElement) attachFields.classList.toggle('hidden', !isAttachment)

        const tenant = modal.querySelector('[data-tenant-adoption-target-tenant]')
        const environment = modal.querySelector('[data-tenant-adoption-target-environment]')
        if (tenant) tenant.textContent = isAttachment ? selected?.dataset.tenantName || '' : ''
        if (environment) environment.textContent = isAttachment ? selected?.dataset.environmentName || '' : ''
    }

    const openModal = (modal, button = opener) => {
        if (!(modal instanceof HTMLElement)) return

        if (button instanceof HTMLElement) opener = button
        syncAdoptionDestination(modal)
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

    document.addEventListener('change', (event) => {
        const destination = event.target
        if (!(destination instanceof HTMLSelectElement) || !destination.matches('[data-tenant-adoption-destination]'))
            return
        syncAdoptionDestination(destination.closest('[data-tenant-adoption-modal]'))
    })

    document.addEventListener('click', (event) => {
        const load = event.target.closest('[data-tenant-adoption-load]')
        if (load) {
            if (!load.disabled) opener = load
            return
        }

        const open = event.target.closest('[data-tenant-adoption-open]')
        if (open) {
            event.preventDefault()
            const id = open.dataset.tenantAdoptionModalId || ''
            const modal = document.getElementById(id)
            if (!open.disabled) openModal(modal, open)
            return
        }

        const close = event.target.closest('[data-tenant-adoption-close]')
        if (close) closeModal(close.closest('[data-tenant-adoption-modal]'))
    })

    document.addEventListener('htmx:afterSwap', (event) => {
        const target = event.target
        if (!(target instanceof HTMLElement) || target.id !== 'tenant-adoption-preflight-slot') return
        const modal = target.querySelector('[data-tenant-adoption-modal]')
        if (modal) openModal(modal)
    })

    document.addEventListener('htmx:responseError', (event) => {
        const load = event.target?.closest?.('[data-tenant-adoption-load]')
        if (load && opener === load) opener = null
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
