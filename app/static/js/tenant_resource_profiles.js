;(() => {
    const form = document.querySelector('[data-tenant-resource-profile-form]')
    const source = document.getElementById('tenant-resource-profile-presets')
    if (!form || !source) return

    const presets = JSON.parse(source.textContent || '{}')
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

    const applyClass = (profileClass) => {
        const custom = profileClass === 'custom'
        const preset = presets[profileClass]

        for (const [name, input] of Object.entries(fields)) {
            input.readOnly = !custom
            input.classList.toggle('bg-surface-hover', !custom)
            if (custom) {
                input.value = ''
                input.placeholder = 'Enter value'
                continue
            }
            input.value = readPath(preset, fieldMap[name]) || ''
            input.placeholder = ''
        }
    }

    form.querySelectorAll('[data-tenant-profile-class]').forEach((radio) => {
        radio.addEventListener('change', () => {
            if (radio.checked) applyClass(radio.value)
        })
    })

    const selected = form.querySelector('[data-tenant-profile-class]:checked')
    if (selected) applyClass(selected.value)
})()
