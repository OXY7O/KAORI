;(() => {
    const fieldMap = {
        requests_cpu: ['quota', 'requests.cpu'],
        limits_cpu: ['quota', 'limits.cpu'],
        requests_memory: ['quota', 'requests.memory'],
        limits_memory: ['quota', 'limits.memory'],
        pods: ['quota', 'pods'],
        persistentvolumeclaims: ['quota', 'persistentvolumeclaims'],
        requests_storage: ['quota', 'requests.storage'],
        services: ['quota', 'services'],
        configmaps: ['quota', 'configmaps'],
        secrets: ['quota', 'secrets'],
        default_request_cpu: ['limits', 'default_request', 'cpu'],
        default_cpu: ['limits', 'default', 'cpu'],
        default_request_memory: ['limits', 'default_request', 'memory'],
        default_memory: ['limits', 'default', 'memory'],
    }

    const readPath = (value, path) => path.reduce((current, key) => current?.[key], value)
    const readJson = (id) => JSON.parse(document.getElementById(id)?.textContent || '{}')

    const collectFields = (form, attribute) =>
        Object.fromEntries(
            Array.from(form.querySelectorAll(`[${attribute}]`)).map((input) => [input.getAttribute(attribute), input])
        )

    const applyValues = (fields, valueSet) => {
        for (const [name, input] of Object.entries(fields)) {
            input.value = valueSet ? readPath(valueSet, fieldMap[name]) || '' : ''
        }
    }

    const setReadonly = (form, fields, readonly) => {
        for (const input of Object.values(fields)) {
            input.readOnly = readonly
            input.setAttribute('aria-readonly', readonly ? 'true' : 'false')
            input.dataset.locked = readonly ? 'true' : 'false'

            const wrapper = input.closest('[data-tenant-resource-field-wrap]')
            const modeLabel = wrapper?.querySelector('[data-tenant-resource-mode-label]')
            const modeText = wrapper?.querySelector('[data-tenant-resource-mode-text]')
            const modeIcon = modeLabel?.querySelector('[data-lucide]')

            if (modeText) modeText.textContent = readonly ? 'Fixed' : 'Editable'
            if (modeIcon) modeIcon.setAttribute('data-lucide', readonly ? 'lock-keyhole' : 'pencil')
            modeLabel?.classList.toggle('bg-surface-hover', readonly)
            modeLabel?.classList.toggle('text-content-muted', readonly)
            modeLabel?.classList.toggle('border-outline-subtle', readonly)
            modeLabel?.classList.toggle('bg-kaori-soft', !readonly)
            modeLabel?.classList.toggle('text-kaori-primary', !readonly)
            modeLabel?.classList.toggle('border-kaori-primary/20', !readonly)
        }

        for (const section of form.querySelectorAll('[data-tenant-resource-section]')) {
            section.classList.toggle('bg-surface-hover', readonly)
            section.classList.toggle('bg-surface-elevated', !readonly)
        }

        const modeTitle = form.querySelector('[data-tenant-profile-mode-title]')
        const modeDetail = form.querySelector('[data-tenant-profile-mode-detail]')
        const modeBadge = form.querySelector('[data-tenant-profile-mode-badge]')
        const modeIcon = form.querySelector('[data-tenant-profile-mode-icon] [data-lucide]')

        if (modeTitle) modeTitle.textContent = readonly ? 'KAORI Preset · Fixed' : 'Custom · Editable'
        if (modeDetail) {
            modeDetail.textContent = readonly
                ? 'Preset values are locked. Choose Custom to edit allocation values.'
                : 'Custom values are operator-managed and validated before use.'
        }
        if (modeBadge) {
            modeBadge.textContent = readonly ? 'Fixed · Locked' : 'Custom · Editable'
            modeBadge.classList.toggle('bg-surface-hover', readonly)
            modeBadge.classList.toggle('text-content-muted', readonly)
            modeBadge.classList.toggle('border-outline-subtle', readonly)
            modeBadge.classList.toggle('bg-kaori-soft', !readonly)
            modeBadge.classList.toggle('text-kaori-primary', !readonly)
            modeBadge.classList.toggle('border-kaori-primary/20', !readonly)
        }
        if (modeIcon) modeIcon.setAttribute('data-lucide', readonly ? 'lock-keyhole' : 'pencil')

        window.lucide?.createIcons?.()
    }

    const initProfileForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const presets = readJson('tenant-resource-profile-presets')
        const classSelect = form.querySelector('[data-tenant-profile-class]')
        const basePreset = form.querySelector('[data-tenant-base-preset]')
        const basePresetWrapper = form.querySelector('[data-tenant-base-preset-wrapper]')
        const fields = collectFields(form, 'data-tenant-resource-field')

        const applyProfileMode = () => {
            const profileClass = classSelect?.value || ''
            const preset = presets[profileClass]

            if (preset) {
                applyValues(fields, preset)
                setReadonly(form, fields, true)
                if (basePreset) {
                    basePreset.value = ''
                    basePreset.disabled = true
                }
                if (basePresetWrapper) basePresetWrapper.hidden = true
                return
            }

            setReadonly(form, fields, false)
            if (basePreset) basePreset.disabled = false
            if (basePresetWrapper) basePresetWrapper.hidden = false
            applyValues(fields, basePreset?.value ? presets[basePreset.value] : null)
        }

        classSelect?.addEventListener('change', applyProfileMode)
        basePreset?.addEventListener('change', () => {
            if (classSelect?.value === 'custom') {
                applyValues(fields, basePreset.value ? presets[basePreset.value] : null)
            }
        })
        applyProfileMode()
    }

    const initCapacityPolicyForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const policies = readJson('tenant-capacity-policy-state')
        const cluster = form.querySelector('[data-capacity-policy-cluster]')
        const fields = collectFields(form, 'data-capacity-policy-field')

        const applyPolicy = () => {
            const policy = policies[cluster?.value] || null
            for (const [name, input] of Object.entries(fields)) {
                const fallback = input.dataset.defaultValue ?? ''
                input.value = policy?.[name] ?? fallback
            }
        }

        cluster?.addEventListener('change', applyPolicy)
        applyPolicy()
    }

    const initAllocationChangeForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const namespaces = readJson('tenant-namespace-allocation-state')
        const namespaceSelect = form.querySelector('[data-tenant-allocation-change-namespace]')
        const profileSelect = form.querySelector('[data-tenant-allocation-change-profile]')

        const currentProfile = form.querySelector('[data-tenant-allocation-current-profile]')
        const currentCpu = form.querySelector('[data-tenant-allocation-current-cpu]')
        const currentMemory = form.querySelector('[data-tenant-allocation-current-memory]')
        const proposedProfile = form.querySelector('[data-tenant-allocation-proposed-profile]')
        const proposedCpu = form.querySelector('[data-tenant-allocation-proposed-cpu]')
        const proposedMemory = form.querySelector('[data-tenant-allocation-proposed-memory]')

        const requestValue = (valueSet, resource) => valueSet?.quota?.[`requests.${resource}`] || 'Unbounded'

        const renderAllocationChange = () => {
            const current = namespaces[namespaceSelect?.value] || null
            const proposed = profiles[profileSelect?.value] || null
            const proposedLabel = profileSelect?.selectedOptions?.[0]?.textContent?.trim() || '—'

            if (currentProfile) {
                currentProfile.textContent = current
                    ? `${current.profile_name} · v${current.profile_version || '—'}`
                    : '—'
            }
            if (currentCpu) currentCpu.textContent = current ? requestValue(current, 'cpu') : '—'
            if (currentMemory) currentMemory.textContent = current ? requestValue(current, 'memory') : '—'
            if (proposedProfile) proposedProfile.textContent = proposed ? proposedLabel : '—'
            if (proposedCpu) proposedCpu.textContent = proposed ? requestValue(proposed, 'cpu') : '—'
            if (proposedMemory) proposedMemory.textContent = proposed ? requestValue(proposed, 'memory') : '—'
        }

        namespaceSelect?.addEventListener('change', renderAllocationChange)
        profileSelect?.addEventListener('change', renderAllocationChange)
        renderAllocationChange()
    }

    const initSharedAllocationForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const tenants = readJson('tenant-capsule-shared-allocation-state')
        const tenantSelect = form.querySelector('[data-tenant-shared-allocation-tenant]')
        const profileSelect = form.querySelector('[data-tenant-shared-allocation-profile]')

        const currentSource = form.querySelector('[data-tenant-shared-current-source]')
        const currentCpu = form.querySelector('[data-tenant-shared-current-cpu]')
        const currentMemory = form.querySelector('[data-tenant-shared-current-memory]')
        const proposedProfile = form.querySelector('[data-tenant-shared-proposed-profile]')
        const proposedCpu = form.querySelector('[data-tenant-shared-proposed-cpu]')
        const proposedMemory = form.querySelector('[data-tenant-shared-proposed-memory]')

        const requestValue = (quota, resource) => quota?.[`requests.${resource}`] || 'Unbounded'

        const render = () => {
            const current = tenants[tenantSelect?.value] || null
            const proposed = profiles[profileSelect?.value] || null
            const proposedLabel = profileSelect?.selectedOptions?.[0]?.textContent?.trim() || '—'
            const source = current?.source || {}

            if (currentSource) {
                currentSource.textContent = current
                    ? `GlobalResourceQuota/${source.name || 'unknown'} · ${current.provider_api_version || 'unknown'}`
                    : '—'
            }
            if (currentCpu) currentCpu.textContent = current ? requestValue(current.current_quota, 'cpu') : '—'
            if (currentMemory) currentMemory.textContent = current ? requestValue(current.current_quota, 'memory') : '—'
            if (proposedProfile) proposedProfile.textContent = proposed ? proposedLabel : '—'
            if (proposedCpu) proposedCpu.textContent = proposed ? requestValue(proposed.quota, 'cpu') : '—'
            if (proposedMemory) proposedMemory.textContent = proposed ? requestValue(proposed.quota, 'memory') : '—'
        }

        tenantSelect?.addEventListener('change', render)
        profileSelect?.addEventListener('change', render)
        render()
    }

    const quotaSummary = (quota) => {
        if (!quota) return '—'
        const parts = [
            ['CPU requests', quota['requests.cpu']],
            ['CPU limits', quota['limits.cpu']],
            ['Memory requests', quota['requests.memory']],
            ['Memory limits', quota['limits.memory']],
            ['Pods', quota.pods],
            ['Storage', quota['requests.storage']],
        ]
            .filter(([, value]) => value !== undefined && value !== null && String(value) !== '')
            .map(([label, value]) => `${label} ${value}`)
        return parts.length ? parts.join(' · ') : 'No bounded supported dimensions'
    }

    const initTenantQuotaCutoverForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const tenants = readJson('tenant-capsule-tenant-quota-state')
        const tenantSelect = form.querySelector('[data-tenant-quota-tenant]')
        const profileSelect = form.querySelector('[data-tenant-quota-profile]')
        const currentSource = form.querySelector('[data-tenant-quota-current-source]')
        const currentScope = form.querySelector('[data-tenant-quota-current-scope]')
        const proposedProfile = form.querySelector('[data-tenant-quota-proposed-profile]')
        const proposedSummary = form.querySelector('[data-tenant-quota-proposed-summary]')

        const render = () => {
            const current = tenants[tenantSelect?.value] || null
            const proposed = profiles[profileSelect?.value] || null
            const proposedLabel = profileSelect?.selectedOptions?.[0]?.textContent?.trim() || '—'
            const source = current?.source || {}
            if (currentSource) {
                currentSource.textContent = current
                    ? `Tenant/${source.name || 'unknown'} · ${source.api_version || 'unknown'}`
                    : '—'
            }
            if (currentScope) {
                currentScope.textContent = current
                    ? `Scope ${current.scope || 'Tenant'} · ${quotaSummary(current.current_quota)}`
                    : '—'
            }
            if (proposedProfile) proposedProfile.textContent = proposed ? proposedLabel : '—'
            if (proposedSummary) proposedSummary.textContent = proposed ? quotaSummary(proposed.quota) : '—'
        }

        tenantSelect?.addEventListener('change', render)
        profileSelect?.addEventListener('change', render)
        render()
    }

    const initTenantQuotaManagedForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const governance = readJson('tenant-capsule-tenant-quota-governance')
        const tenantSelect = form.querySelector('[data-tenant-quota-managed-tenant]')
        const profileSelect = form.querySelector('[data-tenant-quota-managed-profile]')
        const current = form.querySelector('[data-tenant-quota-managed-current]')
        const summary = form.querySelector('[data-tenant-quota-managed-summary]')

        const render = () => {
            const state = governance[tenantSelect?.value] || null
            const proposed = profiles[profileSelect?.value] || null
            const proposedLabel = profileSelect?.selectedOptions?.[0]?.textContent?.trim() || '—'
            if (current) {
                current.textContent = state
                    ? `${state.scope || 'Tenant'} · ${state.provenance || 'kaori_managed'}`
                    : '—'
            }
            if (summary) {
                const currentSummary = state ? quotaSummary(state.desired_quota) : '—'
                const nextSummary = proposed ? quotaSummary(proposed.quota) : '—'
                summary.textContent = proposed
                    ? `Current: ${currentSummary} → Proposed: ${proposedLabel} · ${nextSummary}`
                    : `Current: ${currentSummary}`
            }
        }

        tenantSelect?.addEventListener('change', render)
        profileSelect?.addEventListener('change', render)
        render()
    }

    const initNamespaceForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const select = form.querySelector('[data-tenant-namespace-profile]')
        const fields = collectFields(form, 'data-tenant-namespace-resource-field')
        setReadonly(form, fields, true)

        const applyNamespaceProfile = () => applyValues(fields, profiles[select?.value] || null)
        select?.addEventListener('change', applyNamespaceProfile)
        applyNamespaceProfile()
    }

    const init = (root = document) => {
        const scope = root instanceof Element || root instanceof Document ? root : document
        scope.querySelectorAll('[data-tenant-resource-profile-form]').forEach(initProfileForm)
        scope.querySelectorAll('[data-tenant-capacity-policy-form]').forEach(initCapacityPolicyForm)
        scope.querySelectorAll('[data-tenant-allocation-change-form]').forEach(initAllocationChangeForm)
        scope.querySelectorAll('[data-tenant-shared-allocation-form]').forEach(initSharedAllocationForm)
        scope.querySelectorAll('[data-tenant-quota-allocation-form]').forEach(initTenantQuotaCutoverForm)
        scope.querySelectorAll('[data-tenant-quota-managed-form]').forEach(initTenantQuotaManagedForm)
        scope.querySelectorAll('[data-tenant-namespace-allocation-form]').forEach(initNamespaceForm)
    }

    document.addEventListener('htmx:afterSwap', (event) => init(event.target))
    window.addEventListener('pageshow', () => init())
    init()
})()
