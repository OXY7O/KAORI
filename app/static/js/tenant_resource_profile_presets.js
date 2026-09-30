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
            if (wrapper) wrapper.dataset.locked = readonly ? 'true' : 'false'
            const fixedLabel = wrapper?.querySelector('[data-tenant-resource-mode-fixed]')
            const customLabel = wrapper?.querySelector('[data-tenant-resource-mode-custom]')

            if (fixedLabel) fixedLabel.hidden = !readonly
            if (customLabel) customLabel.hidden = readonly
        }

        const modeTitle = form.querySelector('[data-tenant-profile-mode-title]')
        const modeDetail = form.querySelector('[data-tenant-profile-mode-detail]')
        const fixedModeLabel = form.querySelector('[data-tenant-profile-mode-fixed-label]')
        const customModeLabel = form.querySelector('[data-tenant-profile-mode-custom-label]')
        const modeIcon = form.querySelector('[data-tenant-profile-mode-icon] [data-lucide]')

        if (modeTitle) modeTitle.textContent = readonly ? 'KAORI Preset · Fixed' : 'Custom · Editable'
        if (modeDetail) {
            modeDetail.textContent = readonly
                ? 'Values are fixed; Managed toggles choose which dimensions KAORI owns.'
                : 'Editable values; Managed toggles choose which dimensions KAORI owns.'
        }
        if (fixedModeLabel) fixedModeLabel.hidden = !readonly
        if (customModeLabel) customModeLabel.hidden = readonly
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
        const controls = collectFields(form, 'data-tenant-resource-control')

        const syncManagedState = () => {
            for (const [name, input] of Object.entries(fields)) {
                const managed = controls[name]?.checked !== false
                input.disabled = !managed
                input.setAttribute('aria-disabled', managed ? 'false' : 'true')
                const wrapper = input.closest('[data-tenant-resource-field-wrap]')
                if (wrapper) {
                    wrapper.dataset.controlled = managed ? 'true' : 'false'
                    wrapper.classList.toggle('opacity-60', !managed)
                }
            }
        }

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
                syncManagedState()
                return
            }

            setReadonly(form, fields, false)
            if (basePreset) basePreset.disabled = false
            if (basePresetWrapper) basePresetWrapper.hidden = false
            applyValues(fields, basePreset?.value ? presets[basePreset.value] : null)
            syncManagedState()
        }

        classSelect?.addEventListener('change', applyProfileMode)
        basePreset?.addEventListener('change', () => {
            if (classSelect?.value === 'custom') {
                applyValues(fields, basePreset.value ? presets[basePreset.value] : null)
                syncManagedState()
            }
        })
        Object.values(controls).forEach((control) => control.addEventListener('change', syncManagedState))
        applyProfileMode()
    }

    const initAdvancedControls = (container) => {
        if (!(container instanceof HTMLElement) || container.dataset.kaoriAdvancedInitialized === 'true') return
        container.dataset.kaoriAdvancedInitialized = 'true'

        container.querySelectorAll('[data-tenant-advanced-control-group]').forEach((group) => {
            const key = group.getAttribute('data-tenant-advanced-control-group')
            const toggle = group.querySelector(`[data-tenant-advanced-control-toggle="${key}"]`)
            const fields = Array.from(group.querySelectorAll(`[data-tenant-advanced-control-field="${key}"]`))

            if (!(toggle instanceof HTMLInputElement)) return

            const sync = () => {
                const enabled = toggle.checked
                fields.forEach((field) => {
                    field.disabled = !enabled
                    field.setAttribute('aria-disabled', enabled ? 'false' : 'true')
                })
                group.dataset.enabled = enabled ? 'true' : 'false'
                group.classList.toggle('opacity-70', !enabled)
            }

            toggle.addEventListener('change', sync)
            sync()
        })
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

    const advancedControlSummary = (key, value) => {
        if (!value || value === true || typeof value !== 'object') return ''
        const yesNo = (flag) => (flag ? 'Allow' : 'Deny')

        if (key === 'ingress') {
            return value.enforcement_required === false ? 'Preflight only' : 'Enforcement required'
        }
        if (key === 'service_exposure') {
            if (value.profile_key === 'ingress_only') return 'Ingress only'
            return [
                `ClusterIP ${yesNo(value.allow_cluster_ip)}`,
                `Ingress ${yesNo(value.allow_ingress)}`,
                `NodePort ${yesNo(value.allow_node_port)}`,
                `LoadBalancer ${yesNo(value.allow_load_balancer)}`,
                `ExternalName ${yesNo(value.allow_external_name)}`,
            ].join(' · ')
        }
        if (key === 'hostname_reservation') {
            return [value.match_mode, value.hostname_pattern].filter(Boolean).join(' · ')
        }
        if (key === 'managed_tls' || key === 'managed_registry') {
            return [String(value.mode || '').replaceAll('_', ' '), value.resource_name, value.source_reference]
                .filter(Boolean)
                .join(' · ')
        }
        if (key === 'capsule_namespace_controls') {
            const optionCount = value.namespace_options && typeof value.namespace_options === 'object'
                ? Object.keys(value.namespace_options).length
                : 0
            return `Tenant prefix ${value.force_tenant_prefix ? 'On' : 'Off'} · ${optionCount} namespace option${optionCount === 1 ? '' : 's'}`
        }
        if (key === 'capsule_resource_rules') {
            const registries = Array.isArray(value.container_registries) ? value.container_registries.length : 0
            const priority = Array.isArray(value.priority_classes) ? value.priority_classes.length : 0
            const storage = Array.isArray(value.storage_classes) ? value.storage_classes.length : 0
            return `${registries} registries · ${priority} priority classes · ${storage} storage classes`
        }
        if (key === 'capsule_resource_pools' || key === 'capsule_replication') {
            return [String(value.resource_kind || '').replaceAll('_', ' '), value.resource_name]
                .filter(Boolean)
                .join(' · ')
        }
        if (key === 'capsule_tenant_cordon') {
            return `Cordon ${value.cordoned ? 'On' : 'Off'} · Prevent deletion ${value.prevent_deletion ? 'On' : 'Off'}`
        }
        return ''
    }

    const initNamespaceForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const environments = readJson('tenant-environment-advanced-control-state')
        const profileSelect = form.querySelector('[data-tenant-namespace-profile]')
        const environmentSelect = form.querySelector('[data-tenant-namespace-environment]')
        const providerLabel = form.querySelector('[data-tenant-namespace-provider-label]')
        const fields = collectFields(form, 'data-tenant-namespace-resource-field')
        setReadonly(form, fields, true)

        const renderAdvancedControls = () => {
            const profile = profiles[profileSelect?.value] || null
            const environment = environments[environmentSelect?.value] || null
            const requested = profile?.advanced_controls || {}
            const placementControls = environment?.controls || {}

            if (providerLabel) {
                if (!environment) {
                    providerLabel.textContent = 'No placement selected'
                } else {
                    const provider = environment.provider_key === 'capsule' ? 'Capsule' : 'Native Kubernetes'
                    const state = String(environment.provider_state || '').replaceAll('_', ' ')
                    providerLabel.textContent = state ? `${provider} · ${state}` : provider
                }
            }

            form.querySelectorAll('[data-tenant-namespace-advanced-control]').forEach((card) => {
                const key = card.getAttribute('data-tenant-namespace-advanced-control')
                const toggle = card.querySelector('[data-tenant-namespace-advanced-toggle]')
                const stateLabel = card.querySelector('[data-tenant-namespace-advanced-state]')
                const reason = card.querySelector('[data-tenant-namespace-advanced-reason]')
                const rawRequest = requested[key]
                const isRequested =
                    rawRequest === true ||
                    (rawRequest && typeof rawRequest === 'object' && rawRequest.enabled !== false)
                const placement = placementControls[key] || null
                const configuration = advancedControlSummary(key, rawRequest)
                const isAvailable = isRequested && placement?.state === 'enabled'

                if (toggle) toggle.checked = isRequested
                card.dataset.requested = isRequested ? 'true' : 'false'
                card.dataset.available = isAvailable ? 'true' : 'false'
                card.classList.toggle('opacity-60', isRequested && !isAvailable)

                if (!isRequested) {
                    if (stateLabel) stateLabel.textContent = 'Off'
                    if (reason) reason.textContent = 'Not enabled in the selected Resource Profile.'
                    return
                }

                if (!environment) {
                    if (stateLabel) stateLabel.textContent = 'Select placement'
                    if (reason) {
                        reason.textContent = configuration
                            ? `${configuration}. Choose a Tenant Environment to evaluate provider support.`
                            : 'Choose a Tenant Environment to evaluate provider support.'
                    }
                    return
                }

                if (isAvailable) {
                    if (stateLabel) stateLabel.textContent = 'Enabled'
                    if (reason) {
                        reason.textContent = configuration
                            ? `${configuration}. Supported by the selected provider.`
                            : 'Requested by profile and supported by the selected provider.'
                    }
                    return
                }

                if (stateLabel) stateLabel.textContent = 'Unavailable'
                if (reason) {
                    const unavailableReason = placement?.reason || 'The selected provider cannot enforce this control.'
                    reason.textContent = configuration ? `${configuration}. ${unavailableReason}` : unavailableReason
                }
            })
        }

        const applyNamespaceProfile = () => {
            applyValues(fields, profiles[profileSelect?.value] || null)
            renderAdvancedControls()
        }

        profileSelect?.addEventListener('change', applyNamespaceProfile)
        environmentSelect?.addEventListener('change', renderAdvancedControls)
        applyNamespaceProfile()
    }

    const init = (root = document) => {
        const scope = root instanceof Element || root instanceof Document ? root : document
        scope.querySelectorAll('[data-tenant-resource-profile-form]').forEach(initProfileForm)
        scope.querySelectorAll('[data-tenant-advanced-controls]').forEach(initAdvancedControls)
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
