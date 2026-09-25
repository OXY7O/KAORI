;(() => {
    const form = document.querySelector('[data-tenant-resource-profile-form]')
    const source = document.getElementById('tenant-resource-profile-presets')
    if (!form || !source) return

    const presets = JSON.parse(source.textContent || '{}')
    const select = form.querySelector('[data-tenant-profile-class]')
    const fields = Object.fromEntries(
        Array.from(form.querySelectorAll('[data-tenant-resource-field]')).map((input) => [
            input.dataset.tenantResourceField,
            input,
        ])
    )

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

    const applyPreset = (profileClass) => {
        const preset = presets[profileClass]
        if (!preset) return

        for (const [name, input] of Object.entries(fields)) {
            input.value = readPath(preset, fieldMap[name]) || ''
        }
    }

    select?.addEventListener('change', () => applyPreset(select.value))

    if (select?.value) applyPreset(select.value)
})()
