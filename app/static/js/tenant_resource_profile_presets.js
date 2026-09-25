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

    const setReadonly = (fields, readonly) => {
        for (const input of Object.values(fields)) {
            input.readOnly = readonly
            input.setAttribute('aria-readonly', readonly ? 'true' : 'false')
        }
    }

    const profileForm = document.querySelector('[data-tenant-resource-profile-form]')
    if (profileForm) {
        const presets = readJson('tenant-resource-profile-presets')
        const classSelect = profileForm.querySelector('[data-tenant-profile-class]')
        const basePreset = profileForm.querySelector('[data-tenant-base-preset]')
        const basePresetWrapper = profileForm.querySelector('[data-tenant-base-preset-wrapper]')
        const fields = collectFields(profileForm, 'data-tenant-resource-field')

        const applyProfileMode = () => {
            const profileClass = classSelect?.value || ''
            const preset = presets[profileClass]

            if (preset) {
                applyValues(fields, preset)
                setReadonly(fields, true)
                if (basePreset) {
                    basePreset.value = ''
                    basePreset.disabled = true
                }
                if (basePresetWrapper) basePresetWrapper.hidden = true
                return
            }

            setReadonly(fields, false)
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

    const allocationChangeForm = document.querySelector('[data-tenant-allocation-change-form]')
    if (allocationChangeForm) {
        const profiles = readJson('tenant-namespace-allocation-profiles')
        const namespaces = readJson('tenant-namespace-allocation-state')
        const namespaceSelect = allocationChangeForm.querySelector('[data-tenant-allocation-change-namespace]')
        const profileSelect = allocationChangeForm.querySelector('[data-tenant-allocation-change-profile]')

        const currentProfile = allocationChangeForm.querySelector('[data-tenant-allocation-current-profile]')
        const currentCpu = allocationChangeForm.querySelector('[data-tenant-allocation-current-cpu]')
        const currentMemory = allocationChangeForm.querySelector('[data-tenant-allocation-current-memory]')
        const proposedProfile = allocationChangeForm.querySelector('[data-tenant-allocation-proposed-profile]')
        const proposedCpu = allocationChangeForm.querySelector('[data-tenant-allocation-proposed-cpu]')
        const proposedMemory = allocationChangeForm.querySelector('[data-tenant-allocation-proposed-memory]')

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

    const namespaceForm = document.querySelector('[data-tenant-namespace-allocation-form]')
    if (namespaceForm) {
        const profiles = readJson('tenant-namespace-allocation-profiles')
        const select = namespaceForm.querySelector('[data-tenant-namespace-profile]')
        const fields = collectFields(namespaceForm, 'data-tenant-namespace-resource-field')
        setReadonly(fields, true)

        const applyNamespaceProfile = () => {
            applyValues(fields, profiles[select?.value] || null)
        }

        select?.addEventListener('change', applyNamespaceProfile)
        applyNamespaceProfile()
    }
})()
