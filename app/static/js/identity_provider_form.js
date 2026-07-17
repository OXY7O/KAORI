;(() => {
    const page = document.querySelector('[data-provider-form-page]')
    const form = page?.querySelector('[data-provider-form]')

    if (!page || !form) {
        return
    }

    const providerInputs = Array.from(form.querySelectorAll('[data-provider-type-option]'))
    const ldapPanel = form.querySelector('[data-provider-panel="ldap"]')
    const ssoPanel = form.querySelector('[data-provider-panel="sso"]')
    const googlePolicy = form.querySelector('[data-provider-policy="google"]')
    const githubPolicy = form.querySelector('[data-provider-policy="github"]')
    const jitToggle = form.querySelector('[data-jit-toggle]')
    const jitSettings = form.querySelector('[data-jit-settings]')
    const jitOffNote = form.querySelector('[data-jit-off-note]')
    const keyInput = form.querySelector('#key')
    const typeMeta = page.querySelector('#provider-type-meta')
    const enabledCopy = form.querySelector('[data-enabled-copy]')
    const ssoTitle = form.querySelector('[data-sso-title]')
    const ssoDescription = form.querySelector('[data-sso-description]')
    const ssoClientLabel = form.querySelector('[data-sso-client-label]')
    const ssoSecretInput = form.querySelector('[data-sso-secret-input]')
    const googleIcon = form.querySelector('[data-sso-provider-icon="google"]')
    const githubIcon = form.querySelector('[data-sso-provider-icon="github"]')
    const callbackPanel = page.querySelector('[data-sso-callback]')
    const callbackKey = page.querySelector('[data-callback-key]')

    const labels = {
        ldap: 'LDAP / Active Directory',
        google_oidc: 'Google OpenID Connect',
        github_oauth: 'GitHub OAuth',
    }

    const setControlsEnabled = (container, enabled) => {
        if (!container) {
            return
        }

        container.querySelectorAll('input, select, textarea').forEach((control) => {
            control.disabled = !enabled
        })
    }

    const setPanelState = (panel, visible) => {
        if (!panel) {
            return
        }

        panel.hidden = !visible
        setControlsEnabled(panel, visible)
    }

    const selectedType = () => {
        return providerInputs.find((input) => input.checked)?.value || 'ldap'
    }

    const syncJit = (type) => {
        const ssoActive = type !== 'ldap'
        const enabled = ssoActive && Boolean(jitToggle?.checked)

        if (jitOffNote) {
            jitOffNote.hidden = enabled
        }

        if (jitSettings) {
            jitSettings.hidden = !enabled
            setControlsEnabled(jitSettings, enabled)
        }

        if (googlePolicy) {
            const visible = enabled && type === 'google_oidc'
            googlePolicy.hidden = !visible
            setControlsEnabled(googlePolicy, visible)
        }

        if (githubPolicy) {
            const visible = enabled && type === 'github_oauth'
            githubPolicy.hidden = !visible
            setControlsEnabled(githubPolicy, visible)
        }
    }

    const syncProvider = () => {
        const type = selectedType()
        const isLdap = type === 'ldap'
        const isGoogle = type === 'google_oidc'

        setPanelState(ldapPanel, isLdap)
        setPanelState(ssoPanel, !isLdap)
        syncJit(type)

        page.querySelectorAll('[data-provider-info]').forEach((panel) => {
            panel.hidden = panel.dataset.providerInfo !== type
        })

        if (callbackPanel) {
            callbackPanel.hidden = isLdap
        }

        if (typeMeta) {
            typeMeta.textContent = labels[type] || 'Identity Provider'
        }

        if (enabledCopy) {
            enabledCopy.textContent = isLdap
                ? 'Allow provisioned LDAP identities to use the standard username and password form.'
                : 'Expose this SSO provider on the sign-in page when the client secret is available to the KAORI runtime.'
        }

        if (ssoTitle) {
            ssoTitle.textContent = isGoogle ? 'Google OpenID Connect application' : 'GitHub OAuth application'
        }

        if (ssoDescription) {
            ssoDescription.textContent = isGoogle
                ? 'Register a Web application client in Google and use the exact KAORI callback URI.'
                : 'Register a GitHub OAuth App and use the exact KAORI authorization callback URI.'
        }

        if (ssoClientLabel) {
            ssoClientLabel.textContent = isGoogle ? 'Google Client ID' : 'GitHub Client ID'
        }

        if (ssoSecretInput) {
            ssoSecretInput.placeholder = isGoogle ? 'KAORI_GOOGLE_CLIENT_SECRET' : 'KAORI_GITHUB_CLIENT_SECRET'
        }

        if (googleIcon) {
            googleIcon.hidden = !isGoogle
        }

        if (githubIcon) {
            githubIcon.hidden = isGoogle
        }
    }

    const syncCallback = () => {
        if (callbackKey) {
            callbackKey.textContent = keyInput?.value.trim() || '<provider-key>'
        }
    }

    providerInputs.forEach((input) => input.addEventListener('change', syncProvider))
    jitToggle?.addEventListener('change', () => syncJit(selectedType()))
    keyInput?.addEventListener('input', syncCallback)

    syncProvider()
    syncCallback()
})()
