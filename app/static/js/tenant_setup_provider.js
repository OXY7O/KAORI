;(() => {
    const syncProviderFields = (root = document) => {
        const select =
            root.querySelector?.('#tenant-provider-select') || document.querySelector('#tenant-provider-select')
        const fields =
            root.querySelector?.('[data-capsule-owner-fields]') ||
            document.querySelector('[data-capsule-owner-fields]')
        if (!(select instanceof HTMLSelectElement) || !(fields instanceof HTMLElement)) return

        const capsule = select.value === 'capsule'
        fields.classList.toggle('hidden', !capsule)
        fields.setAttribute('aria-hidden', capsule ? 'false' : 'true')
        fields.querySelectorAll('[data-capsule-owner-control]').forEach((control) => {
            if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement)) return
            control.disabled = !capsule
            control.required = capsule
        })
    }

    document.addEventListener('change', (event) => {
        if (event.target instanceof HTMLSelectElement && event.target.id === 'tenant-provider-select') {
            syncProviderFields(document)
        }
    })

    document.addEventListener('DOMContentLoaded', () => syncProviderFields(document))
    document.addEventListener('htmx:afterSwap', (event) => syncProviderFields(event.target || document))
})()
