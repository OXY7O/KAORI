;(() => {
    const selectedOption = (select) => (select instanceof HTMLSelectElement ? select.selectedOptions[0] || null : null)

    const optionText = (select, fallback = '—') => {
        const option = selectedOption(select)
        const text = option?.textContent?.trim()
        return text || fallback
    }

    const clearSelect = (select) => {
        if (!(select instanceof HTMLSelectElement)) return
        select.value = ''
    }

    const setText = (node, value) => {
        if (node instanceof HTMLElement) node.textContent = value
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
    }

    const syncContext = (
        form,
        {
            membershipOption,
            tenantId,
            tenantName,
            providerKey,
            principalType,
            scopeValue,
            environment,
            namespace,
            environmentCount,
            namespaceCount,
        }
    ) => {
        const profile = form.querySelector('[data-access-profile]')
        const scope = form.querySelector('[data-access-scope]')
        const principal = form.querySelector('[data-access-context-principal]')
        const tenant = form.querySelector('[data-access-context-tenant]')
        const profileContext = form.querySelector('[data-access-context-profile]')
        const scopeContext = form.querySelector('[data-access-context-scope]')
        const providerContext = form.querySelector('[data-access-context-provider]')

        const subjectName = membershipOption?.dataset.subjectName || ''
        const principalLabel = principalType
            ? `${subjectName || 'Selected principal'} · ${principalType.replaceAll('_', ' ')}`
            : 'Select Membership'
        setText(principal, principalLabel)
        setText(tenant, tenantId ? tenantName : 'Not resolved')
        setText(profileContext, optionText(profile, 'No compatible profile'))

        const scopeLabel = optionText(scope, 'Namespace')
        let targetLabel = 'target pending'
        if (!tenantId) {
            targetLabel = 'select Membership first'
        } else if (scopeValue === 'tenant') {
            targetLabel = tenantName
        } else if (scopeValue === 'environment') {
            targetLabel = environment?.value ? optionText(environment, 'target pending') : 'target pending'
        } else {
            targetLabel = namespace?.value ? optionText(namespace, 'target pending') : 'target pending'
        }
        setText(scopeContext, `${scopeLabel} · ${targetLabel}`)

        let providerMessage =
            'Select a Membership to resolve provider authority. KAORI validates Tenant and scope before commit.'
        if (tenantId && providerKey && providerKey !== 'native_kubernetes') {
            providerMessage = `${tenantName} uses Capsule authority. Access Grant reconciliation is not admitted yet, so provider mutation remains blocked.`
        } else if (tenantId && scopeValue === 'namespace' && namespaceCount === 0) {
            providerMessage = `No governed Namespace exists in ${tenantName}. Provision a Namespace before applying Namespace-scoped access.`
        } else if (tenantId && scopeValue === 'environment' && environmentCount === 0) {
            providerMessage = `No governed Environment target is available in ${tenantName}. The grant remains blocked until a valid target exists.`
        } else if (tenantId) {
            providerMessage =
                'Native Kubernetes authority selected. KAORI commits the grant and reconciles namespaced RBAC only within this Tenant and scope.'
        }
        setText(providerContext, providerMessage)
    }

    const syncForm = (form) => {
        if (!(form instanceof HTMLFormElement)) return

        const membership = form.querySelector('[data-access-membership]')
        const scope = form.querySelector('[data-access-scope]')
        const environmentField = form.querySelector('[data-access-environment-field]')
        const namespaceField = form.querySelector('[data-access-namespace-field]')
        const environment = form.querySelector('[data-access-environment]')
        const namespace = form.querySelector('[data-access-namespace]')
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

        syncContext(form, {
            membershipOption,
            tenantId,
            tenantName,
            providerKey,
            principalType,
            scopeValue,
            environment,
            namespace,
            environmentCount,
            namespaceCount,
        })
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
            target.matches('[data-access-scope]') ||
            target.matches('[data-access-environment]') ||
            target.matches('[data-access-namespace]')
        ) {
            syncForm(form)
        }
    })

    document.addEventListener('htmx:afterSwap', (event) => init(event.target))
    window.addEventListener('pageshow', () => init())
    init()
})()
