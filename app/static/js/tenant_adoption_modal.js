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
        delete modal.dataset.tenantAdoptionActivated
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
        // Preflight HTML is intentionally visible as soon as HTMX inserts it.
        // JS enhances focus/body scrolling once per response, not visibility.
        if (modal.dataset.tenantAdoptionActivated !== 'true') {
            modal.dataset.tenantAdoptionActivated = 'true'
            openModal(modal)
        }
        preflightPending = false
        return true
    }

    // Report request evidence, not a generic "modal did not load" guess.
    // Do not echo responseText (may contain internal Flask/Ingress error details).
    const reportPreflightFailure = (event, kind = 'response') => {
        const slot = document.getElementById('tenant-adoption-preflight-slot')
        const status = Number(event.detail?.xhr?.status || 0)
        if (slot && !slot.querySelector('[data-tenant-adoption-modal]')) {
            const message = document.createElement('div')
            message.setAttribute('role', 'alert')
            message.setAttribute('data-tenant-adoption-request-error', '')
            message.className =
                'rounded-xl border border-status-warning-border bg-status-warning-soft p-4 text-sm text-status-warning-text'

            const title = document.createElement('p')
            title.className = 'font-semibold'
            title.textContent = status ? `Adoption preflight request failed (HTTP ${status}).` :
                'Adoption preflight request could not complete.'

            const guidance = document.createElement('p')
            guidance.className = 'mt-2 text-xs leading-5'
            if (status === 401 || status === 403) {
                guidance.textContent = 'Authentication or Tenant management permission was rejected. Review your session and permissions before retrying.'
            } else if (status === 404) {
                guidance.textContent = 'The preflight endpoint was not found. Verify the running DevContainer app and its route.'
            } else if (status >= 500) {
                guidance.textContent = 'The server failed while preparing read-only provider evidence. Check the DevContainer application logs for GET /discovery/preflight; do not submit Adoption.'
            } else if (kind === 'target') {
                guidance.textContent = 'The Discovery preflight response target is missing. Refresh Discovery before retrying.'
            } else if (kind === 'swap') {
                guidance.textContent = 'The preflight response could not be rendered. Inspect the browser Console and Network response.'
            } else {
                guidance.textContent = 'Inspect the GET /discovery/preflight request in browser Network for its status and response; retry after resolving the failure.'
            }
            message.append(title, guidance)
            slot.replaceChildren(message)
            message.scrollIntoView?.({ block: 'nearest' })
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

    document.addEventListener('htmx:beforeRequest', (event) => {
        const requestElement = event.detail?.elt || event.target
        if (!(requestElement instanceof HTMLElement) || !requestElement.matches('[data-tenant-adoption-load]'))
            return
        opener = requestElement
        preflightPending = true
    })

    document.addEventListener('htmx:afterSwap', (event) => {
        revealPreflight(event)
    })

    // Fallback for HTMX versions/events that expose the swap target in
    // afterSettle or afterRequest only. Once opened, later events do not reopen it.
    document.addEventListener('htmx:afterSettle', (event) => {
        if (preflightPending) revealPreflight(event)
    })

    const isPreflightRequest = (event) =>
        Boolean(event.detail?.elt?.closest?.('[data-tenant-adoption-load]') ||
            event.target?.closest?.('[data-tenant-adoption-load]'))

    document.addEventListener('htmx:responseError', (event) => {
        if (isPreflightRequest(event)) reportPreflightFailure(event)
    })
    for (const kind of ['sendError', 'timeout', 'abort', 'targetError', 'swapError']) {
        document.addEventListener(`htmx:${kind}`, (event) => {
            if (isPreflightRequest(event) || (preflightPending && kind === 'targetError'))
                reportPreflightFailure(event, kind === 'targetError' ? 'target' : 'swap')
        })
    }

    document.addEventListener('htmx:afterRequest', (event) => {
        const requestElement = event.detail?.elt || event.target
        if (requestElement?.matches?.('[data-tenant-adoption-load]')) {
            if (event.detail?.successful === false) reportPreflightFailure(event)
            // A successful afterRequest may precede the HTML swap. Wait for
            // afterSwap/afterSettle instead of showing a false error.
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
