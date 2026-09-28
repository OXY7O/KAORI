;(() => {
    const profileCopy = {
        viewer: 'Viewer — read-only visibility for workloads and namespace resources.',
        operator: 'Operator — workload/application operations without namespaced Secret write access.',
        tenant_admin: 'Tenant Admin — Operator capabilities plus namespaced Secret management.',
        deployer: 'Deployer — automation-only profile for ServiceAccount memberships.',
    }

    const selectedOption = (select) => (select instanceof HTMLSelectElement ? select.selectedOptions[0] || null : null)

    const clearSelect = (select) => {
        if (!(select instanceof HTMLSelectElement)) return
        select.value = ''
    }

    const filterTenantOptions = (select, tenantId) => {
        if (!(select instanceof HTMLSelectElement)) return 0
        let selectedStillValid = !select.value
        let eligibleCount = 0
        for (const option of select.options) {
            if (!option.dataset.tenantId) continue
            const eligible = Boolean(tenantId) && option.dataset.tenantId === tenantId
            option.hidden = !eligible
            option.disabled = !eligible
            if (eligible) eligibleCount += 1
            if (eligible && option.selected) selectedStillValid = true
        }
        if (!selectedStillValid) clearSelect(select)
        return eligibleCount
    }

    const syncProfiles = (form, principalType) => {
        const normalizedPrincipalType = String(principalType || '')
            .trim()
            .toLowerCase()
        const profile = form.querySelector('[data-access-profile]')
        const guidance = form.querySelector('[data-access-profile-guidance]')
        if (!(profile instanceof HTMLSelectElement)) return

        let selectedStillValid = false
        for (const option of profile.options) {
            const types = (option.dataset.principalTypes || '')
                .split(',')
                .map((value) => value.trim().toLowerCase())
                .filter(Boolean)
            const eligible = !normalizedPrincipalType || types.includes(normalizedPrincipalType)
            option.hidden = !eligible
            option.disabled = !eligible
            if (eligible && option.selected) selectedStillValid = true
        }

        if (!selectedStillValid) {
            const firstEligible = [...profile.options].find((option) => !option.disabled)
            profile.value = firstEligible?.value || ''
        }

        const current = selectedOption(profile)
        if (guidance) {
            guidance.textContent = normalizedPrincipalType
                ? profileCopy[current?.value] || 'Choose the least-privilege profile required by this principal.'
                : 'Select Membership first; incompatible profiles are filtered automatically.'
        }
    }

    const syncForm = (form) => {
        if (!(form instanceof HTMLFormElement)) return

        const membership = form.querySelector('[data-access-membership]')
        const scope = form.querySelector('[data-access-scope]')
        const environmentField = form.querySelector('[data-access-environment-field]')
        const namespaceField = form.querySelector('[data-access-namespace-field]')
        const environment = form.querySelector('[data-access-environment]')
        const namespace = form.querySelector('[data-access-namespace]')
        const scopeGuidance = form.querySelector('[data-access-scope-guidance]')
        const providerWarning = form.querySelector('[data-access-provider-warning]')
        const submit = form.querySelector('[data-access-submit]')

        if (!(membership instanceof HTMLSelectElement) || !(scope instanceof HTMLSelectElement)) return

        const membershipOption = selectedOption(membership)
        const tenantId = membershipOption?.dataset.tenantId || ''
        const tenantName = membershipOption?.dataset.tenantName || 'the selected Tenant'
        const providerKey = String(membershipOption?.dataset.providerKey || '')
            .trim()
            .toLowerCase()
        const principalType = membershipOption?.dataset.principalType || ''
        const scopeValue = scope.value

        syncProfiles(form, principalType)
        const environmentCount = filterTenantOptions(environment, tenantId)
        const namespaceCount = filterTenantOptions(namespace, tenantId)

        const showEnvironment = scopeValue === 'environment'
        const showNamespace = scopeValue === 'namespace'

        if (environmentField instanceof HTMLElement) environmentField.hidden = !showEnvironment
        if (namespaceField instanceof HTMLElement) namespaceField.hidden = !showNamespace

        if (environment instanceof HTMLSelectElement) {
            environment.disabled = !showEnvironment || !tenantId
            environment.required = showEnvironment && Boolean(tenantId)
            if (!showEnvironment) clearSelect(environment)
        }
        if (namespace instanceof HTMLSelectElement) {
            namespace.disabled = !showNamespace || !tenantId
            namespace.required = showNamespace && Boolean(tenantId)
            if (!showNamespace) clearSelect(namespace)
        }

        const providerSupported = !providerKey || providerKey === 'native_kubernetes'
        const namespaceReady = scopeValue !== 'namespace' || namespaceCount > 0
        const environmentReady = scopeValue !== 'environment' || environmentCount > 0
        if (providerWarning instanceof HTMLElement) providerWarning.hidden = providerSupported
        if (submit instanceof HTMLButtonElement) {
            const enabled = Boolean(tenantId) && providerSupported && namespaceReady && environmentReady
            submit.disabled = !enabled
            submit.setAttribute('aria-disabled', enabled ? 'false' : 'true')
        }

        if (!scopeGuidance) return
        if (!tenantId) {
            scopeGuidance.textContent =
                'Select Membership first. KAORI will restrict targets to that Membership’s Tenant.'
        } else if (!providerSupported) {
            scopeGuidance.textContent =
                tenantName +
                ' uses Capsule authority. Access Grant provider reconciliation remains fail-closed until the Capsule access adapter is admitted.'
        } else if (scopeValue === 'namespace' && namespaceCount === 0) {
            scopeGuidance.textContent =
                'No governed namespace exists in ' +
                tenantName +
                '. Provision Namespace first, then return to Namespace scope.'
        } else if (scopeValue === 'tenant') {
            scopeGuidance.textContent = `Tenant scope — applies the profile across all governed namespaces in ${tenantName}. No target selection is required.`
        } else if (scopeValue === 'environment') {
            scopeGuidance.textContent = `Environment scope — choose one environment from ${tenantName}; all governed namespaces in that environment are targeted.`
        } else {
            scopeGuidance.textContent = `Namespace scope — choose exactly one namespace from ${tenantName}; this is the narrowest authorization boundary.`
        }
    }

    const init = (root = document) => {
        const forms = root.querySelectorAll?.('[data-access-grant-form]') || []
        for (const form of forms) syncForm(form)
        if (root.matches?.('[data-access-grant-form]')) syncForm(root)
    }

    document.addEventListener('change', (event) => {
        const target = event.target
        if (!(target instanceof HTMLSelectElement)) return
        const form = target.closest('[data-access-grant-form]')
        if (!form) return
        if (
            target.matches('[data-access-membership]') ||
            target.matches('[data-access-profile]') ||
            target.matches('[data-access-scope]')
        ) {
            syncForm(form)
        }
    })

    document.addEventListener('htmx:afterSwap', (event) => init(event.target))
    window.addEventListener('pageshow', () => init())
    init()
})()
