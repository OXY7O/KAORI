;(() => {
    const form = document.querySelector('[data-tenant-profile-form]')
    const dataNode = document.getElementById('tenant-profile-presets')
    if (!form || !dataNode) return

    const presets = JSON.parse(dataNode.textContent || '{}')
    const mapping = {
        'requests.cpu': 'requests_cpu',
        'limits.cpu': 'limits_cpu',
        'requests.memory': 'requests_memory',
        'limits.memory': 'limits_memory',
        pods: 'pods',
        persistentvolumeclaims: 'persistentvolumeclaims',
        'requests.storage': 'requests_storage',
        services: 'services',
        configmaps: 'configmaps',
        secrets: 'secrets',
    }
    const limitMapping = {
        default_request: {
            cpu: 'default_request_cpu',
            memory: 'default_request_memory',
        },
        default: {
            cpu: 'default_cpu',
            memory: 'default_memory',
        },
    }

    const resourceInputs = [...form.querySelectorAll('[data-profile-value]')]

    function applyProfileClass(profileClass) {
        const custom = profileClass === 'custom'
        resourceInputs.forEach((input) => {
            input.readOnly = !custom
            input.setAttribute('aria-readonly', custom ? 'false' : 'true')
            input.classList.toggle('bg-surface-elevated', !custom)
        })

        if (custom) {
            resourceInputs.forEach((input) => {
                input.value = ''
            })
            return
        }

        const preset = presets[profileClass]
        if (!preset) return

        Object.entries(preset.quota_hard || {}).forEach(([key, value]) => {
            const name = mapping[key]
            if (name && form.elements[name]) form.elements[name].value = value
        })
        Object.entries(limitMapping).forEach(([group, fields]) => {
            Object.entries(fields).forEach(([resource, name]) => {
                const value = preset.limit_defaults?.[group]?.[resource] || ''
                if (form.elements[name]) form.elements[name].value = value
            })
        })
    }

    form.querySelectorAll('input[name="profile_class"]').forEach((radio) => {
        radio.addEventListener('change', () => {
            if (radio.checked) applyProfileClass(radio.value)
        })
    })

    const selected = form.querySelector('input[name="profile_class"]:checked')
    if (selected) applyProfileClass(selected.value)
})()
