;(() => {
    const page = document.querySelector('[data-provider-form-page]')
    const form = page?.querySelector('[data-provider-form]')
    if (!page || !form) return

    const providerInputs = Array.from(form.querySelectorAll('input[type="radio"][data-provider-option]'))
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
    const registrationProof = form.querySelector('[data-registration-proof]')
    const registrationSave = form.querySelector('[data-registration-save]')
    const registrationStatus = form.querySelector('[data-connection-test-state]')
    const syncRegistrationGate = () => {
        if (!registrationProof || !registrationSave) return
        const verified = Boolean(registrationProof.value)
        registrationSave.disabled = !verified
        registrationSave.setAttribute('aria-disabled', String(!verified))
        registrationSave.title = verified
            ? 'Save this tested provider configuration'
            : 'Complete Test Connection before saving'
        if (registrationStatus)
            registrationStatus.textContent = verified
                ? 'Connection Verified — configuration ready to save.'
                : 'Connection Test Required — test this configuration before saving.'
    }
    const invalidateRegistrationTest = (event) => {
        if (!registrationProof) return
        if (['csrf_token', 'connection_test_proof'].includes(event.target?.name)) return
        registrationProof.value = ''
        syncRegistrationGate()
    }

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
        // The radio and label are siblings. Nested badge elements cannot use peer-checked
        // directly, so reflect the native checked state using this existing controller.
        providerInputs.forEach((input) => {
            const badge = input.nextElementSibling?.querySelector('[data-provider-option-badge]')
            if (!badge) return
            const selected = input.checked
            const status = badge.querySelector('[data-provider-option-status]')
            if (status) status.textContent = selected ? 'Selected' : 'Select'
            badge.classList.toggle('border-brand-outline', selected)
            badge.classList.toggle('border-outline-default', !selected)
            badge.classList.toggle('text-kaori-primary', selected)
            badge.classList.toggle('text-content-muted', !selected)
        })
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
        // Re-query the live display icon: Lucide replaces <i> with <svg> after each render.
        // Provider radios only carry data-provider-option-icon and must never receive data-lucide.
        const providerIcon = form.querySelector(
            '[data-configuration-panel="browser_client"] [data-provider-display-icon]'
        )
        if (providerIcon) providerIcon.dataset.lucide = option?.dataset.providerOptionIcon || 'log-in'
        syncJit(option)
        if (window.lucide) window.lucide.createIcons()
    }

    const syncCallback = () => {
        if (callbackKey) callbackKey.textContent = keyInput?.value.trim() || '<provider-key>'
    }

    form.addEventListener('input', invalidateRegistrationTest, true)
    form.addEventListener('change', invalidateRegistrationTest, true)
    syncRegistrationGate()

    providerInputs.forEach((input) => input.addEventListener('change', syncProvider))
    jitToggle?.addEventListener('change', () => syncJit(selectedOption()))
    keyInput?.addEventListener('input', syncCallback)
    syncProvider()
    syncCallback()
})()
