;(() => {
    const page = document.querySelector('[data-provider-form-page]')
    const form = page?.querySelector('[data-provider-form]')
    if (!page || !form) return

    const providerInputs = Array.from(form.querySelectorAll('[data-provider-option]'))
    const configurationPanels = Array.from(form.querySelectorAll('[data-configuration-panel]'))
    const guidancePanels = Array.from(form.querySelectorAll('[data-provider-guidance]'))
    const jitToggle = form.querySelector('[data-jit-toggle]')
    const jitSettings = form.querySelector('[data-jit-settings]')
    const jitOffNote = form.querySelector('[data-jit-off-note]')
    const admissionField = form.querySelector('[data-admission-policy-field]')
    const admissionLabel = form.querySelector('[data-admission-label]')
    const admissionHelp = form.querySelector('[data-admission-help]')
    const clientSecretInput = form.querySelector('[data-client-secret-input]')
    const browserCallback = page.querySelector('[data-browser-callback]')
    const callbackKey = page.querySelector('[data-callback-key]')
    const keyInput = form.querySelector('#key')
    const typeMeta = page.querySelector('#provider-type-meta')
    const enabledCopy = form.querySelector('[data-enabled-copy]')
    const browserTitle = form.querySelector('[data-browser-title]')
    const providerIcon = form.querySelector('[data-provider-icon]')

    const selectedOption = () => providerInputs.find((input) => input.checked) || null

    const setControlsEnabled = (container, enabled) => {
        if (!container) return
        container.querySelectorAll('input, select, textarea').forEach((control) => {
            control.disabled = !enabled
        })
    }

    const syncJit = (option) => {
        const supportsJit = option?.dataset.flow === 'browser'
        if (jitToggle) {
            jitToggle.disabled = !supportsJit
            if (!supportsJit) jitToggle.checked = false
        }
        const enabled = supportsJit && Boolean(jitToggle?.checked)
        if (jitOffNote) jitOffNote.hidden = enabled || !supportsJit
        if (jitSettings) {
            jitSettings.hidden = !enabled
            setControlsEnabled(jitSettings, enabled)
        }
        if (admissionField) admissionField.hidden = !enabled
    }

    const syncProvider = () => {
        const option = selectedOption()
        const profile = option?.dataset.configurationProfile || ''
        const flow = option?.dataset.flow || ''

        configurationPanels.forEach((panel) => {
            const visible = panel.dataset.configurationPanel === profile
            panel.hidden = !visible
            setControlsEnabled(panel, visible)
        })
        guidancePanels.forEach((panel) => {
            panel.hidden = panel.id !== option?.dataset.guidanceTarget
        })
        if (browserCallback) browserCallback.hidden = flow !== 'browser'
        if (typeMeta) typeMeta.textContent = option?.dataset.providerLabel || 'Select Provider'
        if (enabledCopy)
            enabledCopy.textContent = option?.dataset.enabledCopy || 'Select a provider before enabling authentication.'
        if (admissionLabel) admissionLabel.textContent = option?.dataset.admissionLabel || 'Admission Policy Values'
        if (admissionHelp)
            admissionHelp.textContent =
                option?.dataset.admissionHelp || 'Values are evaluated by the selected admission policy.'
        if (clientSecretInput)
            clientSecretInput.placeholder = option?.dataset.clientSecretPlaceholder || 'KAORI_IDP_CLIENT_SECRET'
        if (browserTitle)
            browserTitle.textContent = option
                ? `${option.dataset.providerLabel} Application`
                : 'Browser SSO Application'
        if (providerIcon) providerIcon.dataset.lucide = option?.dataset.providerIcon || 'log-in'
        syncJit(option)
        if (window.lucide) window.lucide.createIcons()
    }

    const syncCallback = () => {
        if (callbackKey) callbackKey.textContent = keyInput?.value.trim() || '<provider-key>'
    }

    providerInputs.forEach((input) => input.addEventListener('change', syncProvider))
    jitToggle?.addEventListener('change', () => syncJit(selectedOption()))
    keyInput?.addEventListener('input', syncCallback)
    syncProvider()
    syncCallback()
})()
