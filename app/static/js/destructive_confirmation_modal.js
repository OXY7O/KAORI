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

    const visibleModal = () => document.querySelector('[data-destructive-confirmation-modal]:not(.hidden)')

    const applyDynamicPayload = (modal, button) => {
        const form = modal.querySelector('[data-destructive-dynamic-form]')
        const deleteUrl = button.dataset.deleteUrl || ''
        if (form instanceof HTMLFormElement) {
            form.setAttribute('action', deleteUrl)
            if (deleteUrl) {
                form.setAttribute('hx-post', deleteUrl)
                if (window.htmx) window.htmx.process(form)
            } else {
                form.removeAttribute('hx-post')
            }
        }

        const title = modal.querySelector('[data-destructive-modal-title]')
        const targetName = modal.querySelector('[data-destructive-target-name]')
        const detail = modal.querySelector('[data-destructive-detail]')
        const actionLabel = modal.querySelector('[data-destructive-action-label]')

        if (title && button.dataset.deleteTitle) title.textContent = button.dataset.deleteTitle
        if (targetName && button.dataset.deleteName) targetName.textContent = button.dataset.deleteName
        if (detail && button.dataset.deleteDetail) detail.textContent = button.dataset.deleteDetail
        if (actionLabel && button.dataset.deleteActionLabel) actionLabel.textContent = button.dataset.deleteActionLabel
    }

    const resetDynamicForm = (modal) => {
        const form = modal.querySelector('[data-destructive-dynamic-form]')
        if (!(form instanceof HTMLFormElement)) return
        form.setAttribute('action', '')
        form.removeAttribute('hx-post')
    }

    const openModal = (button) => {
        const modal = document.getElementById(button.dataset.destructiveModalId || '')
        if (!(modal instanceof HTMLElement)) return
        opener = button
        const targetSelector = button.dataset.destructiveTargetInput
        const target = targetSelector ? document.querySelector(targetSelector) : null
        const output = modal.querySelector('[data-destructive-target-name]')
        if (output)
            output.textContent = target?.value?.trim() || button.dataset.destructiveTarget || 'Selected Resource'
        const form = button.closest('form')
        const cluster = form?.querySelector('[name="cluster_id"]')
        const namespace = form?.querySelector('[name="namespace"]')
        const clusterLabel =
            cluster instanceof HTMLSelectElement
                ? cluster.selectedOptions[0]?.textContent?.trim()
                : cluster?.value?.trim()
        const namespaceLabel = namespace?.value?.trim()
        const scope = modal.querySelector('[data-destructive-target-scope]')
        if (scope) {
            scope.textContent =
                button.dataset.destructiveScope ||
                [clusterLabel, namespaceLabel].filter(Boolean).join(' / ') ||
                scope.textContent ||
                'Operational target'
        }
        applyDynamicPayload(modal, button)
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
        resetDynamicForm(modal)
        opener?.focus()
        opener = null
    }

    document.addEventListener('click', (event) => {
        const open = event.target.closest('[data-destructive-modal-open]')
        if (open) {
            event.preventDefault()
            if (!open.disabled) openModal(open)
            return
        }
        const close = event.target.closest('[data-destructive-modal-close]')
        if (close) {
            closeModal(close.closest('[data-destructive-confirmation-modal]'))
            return
        }
        const confirm = event.target.closest('[data-destructive-modal-confirm]')
        if (confirm) {
            const modal = confirm.closest('[data-destructive-confirmation-modal]')
            const submitButtonId = opener?.dataset.destructiveSubmitButtonId || confirm.dataset.submitButtonId || ''
            const submit = document.getElementById(submitButtonId)
            closeModal(modal)
            submit?.click()
        }
    })

    document.addEventListener('htmx:afterRequest', (event) => {
        const form =
            event.target instanceof HTMLFormElement
                ? event.target
                : event.target?.closest?.('[data-destructive-dynamic-form]')
        if (!(form instanceof HTMLFormElement) || !form.matches('[data-destructive-dynamic-form]')) return
        closeModal(form.closest('[data-destructive-confirmation-modal]'))
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
