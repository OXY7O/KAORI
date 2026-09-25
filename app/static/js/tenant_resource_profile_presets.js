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

    const bindInitialFill = ({ formSelector, sourceId, selectSelector, fieldAttribute }) => {
        const form = document.querySelector(formSelector)
        const source = document.getElementById(sourceId)
        if (!form || !source) return

        const values = JSON.parse(source.textContent || '{}')
        const select = form.querySelector(selectSelector)
        const fields = Object.fromEntries(
            Array.from(form.querySelectorAll(`[${fieldAttribute}]`)).map((input) => [
                input.getAttribute(fieldAttribute),
                input,
            ])
        )

        const apply = (key) => {
            const valueSet = values[key]
            for (const [name, input] of Object.entries(fields)) {
                input.value = valueSet ? readPath(valueSet, fieldMap[name]) || '' : ''
            }
        }

        select?.addEventListener('change', () => apply(select.value))
        if (select?.value) apply(select.value)
    }

    bindInitialFill({
        formSelector: '[data-tenant-resource-profile-form]',
        sourceId: 'tenant-resource-profile-presets',
        selectSelector: '[data-tenant-profile-class]',
        fieldAttribute: 'data-tenant-resource-field',
    })

    bindInitialFill({
        formSelector: '[data-tenant-namespace-allocation-form]',
        sourceId: 'tenant-namespace-allocation-profiles',
        selectSelector: '[data-tenant-namespace-profile]',
        fieldAttribute: 'data-tenant-namespace-resource-field',
    })
})()
