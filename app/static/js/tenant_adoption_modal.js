;(() => {
    let opener = null
    let preflightPending = false
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
            createFields.classList.toggle('grid', !isAttachment)
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
        // Make the dialog visible before adjusting mode-specific fields, so
        // presentation synchronization cannot suppress the entire preflight.
        modal.classList.remove('hidden')
        modal.classList.add('flex')
        modal.setAttribute('aria-hidden', 'false')
        document.documentElement.classList.add('overflow-hidden')

        const dialog = modal.querySelector('[role="dialog"]')
        syncAdoptionDestination(modal)
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

    // HTMX may report the swap target through event.detail.target rather than
    // the dispatched event target. Accept either and only open the new preflight
    // for its owning slot; do not depend on timing or page-specific rebinding.
    const preflightSlotFrom = (event) => {
        const target = event.detail?.target || event.target
        if (!(target instanceof HTMLElement)) return null
        if (target.id === 'tenant-adoption-preflight-slot') return target
        if (target.matches?.('[data-tenant-adoption-load]'))
            return document.getElementById('tenant-adoption-preflight-slot')
        return null
    }

    const revealPreflight = (event) => {
        const slot = preflightSlotFrom(event)
        if (!slot) return false
        const modal = slot.querySelector('[data-tenant-adoption-modal]')
        if (!(modal instanceof HTMLElement)) return false
        if (modal.classList.contains('hidden')) openModal(modal)
        preflightPending = false
        return true
    }

    const reportPreflightFailure = () => {
        const slot = document.getElementById('tenant-adoption-preflight-slot')
        if (slot && !slot.querySelector('[data-tenant-adoption-modal]')) {
            const notice = document.createElement('p')
            notice.setAttribute('role', 'alert')
            notice.className =
                'rounded-xl border border-status-warning-border bg-status-warning-soft p-4 text-sm text-status-warning-text'
            notice.textContent =
                'Adoption preflight could not be loaded. Check the request and refresh Discovery before retrying.'
            slot.replaceChildren(notice)
            notice.scrollIntoView?.({ block: 'nearest' })
        }
        preflightPending = false
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
            if (!load.disabled) {
                opener = load
                preflightPending = true
            }
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
        revealPreflight(event)
    })

    // Fallback for HTMX versions/events that expose the swap target in
    // afterSettle or afterRequest only. Once opened, later events do not reopen it.
    document.addEventListener('htmx:afterSettle', (event) => {
        if (preflightPending) revealPreflight(event)
    })

    document.addEventListener('htmx:responseError', (event) => {
        const load = event.detail?.elt?.closest?.('[data-tenant-adoption-load]') ||
            event.target?.closest?.('[data-tenant-adoption-load]')
        if (load && preflightPending) reportPreflightFailure()
    })

    document.addEventListener('htmx:afterRequest', (event) => {
        const requestElement = event.detail?.elt || event.target
        if (requestElement?.matches?.('[data-tenant-adoption-load]')) {
            if (!preflightPending) return
            if (event.detail?.successful === false) {
                reportPreflightFailure()
                return
            }
            if (!revealPreflight(event)) reportPreflightFailure()
            return
        }
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
