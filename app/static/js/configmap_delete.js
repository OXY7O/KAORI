;(() => {
    const formSelector = '#configmap-delete-form'

    const resetValidationPreview = (form) => {
        const preview = form.querySelector('[data-configmap-validation-preview]')
        const template = document.getElementById('configmap-validation-pending-template')
        if (!(preview instanceof HTMLElement) || !(template instanceof HTMLTemplateElement)) return

        preview.replaceChildren(template.content.cloneNode(true))
        preview.dataset.validationStatus = 'pending'
        preview.className = 'rounded-xl border border-outline-default bg-surface-card p-4 sm:p-5'
        window.renderKaoriIcons?.()
    }

    const invalidateDeleteValidation = (form) => {
        if (!(form instanceof HTMLFormElement)) return

        form.querySelector('[data-configmap-delete-validation-token]')?.remove()
        const finalAction = form.querySelector('[data-configmap-delete-final-action]')
        if (finalAction instanceof HTMLButtonElement) {
            finalAction.disabled = true
            finalAction.setAttribute('aria-disabled', 'true')
            finalAction.setAttribute('title', 'Validate deletion after the latest target or confirmation change')
        }

        const label = form.querySelector('[data-configmap-delete-validation-label]')
        if (label) label.textContent = 'Validate Deletion'
        resetValidationPreview(form)
    }

    const handleMutation = (event) => {
        const target = event.target
        if (!(target instanceof Element)) return
        const form = target.closest(formSelector)
        if (!(form instanceof HTMLFormElement)) return
        if (target.matches('[name="operation"]')) return
        invalidateDeleteValidation(form)
    }

    document.addEventListener('input', handleMutation)
    document.addEventListener('change', handleMutation)
})()
