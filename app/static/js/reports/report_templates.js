;(function () {
    'use strict'

    const parseConfig = () => {
        const configNode = document.getElementById('report-templates-config-data')
        if (!configNode) {
            console.error('KAORI Report Templates configuration is unavailable.')
            return null
        }

        const configPayload = configNode.content?.textContent ?? configNode.textContent
        if (!configPayload?.trim()) {
            console.error('KAORI Report Templates configuration is unavailable.')
            return null
        }

        try {
            return JSON.parse(configPayload)
        } catch (error) {
            console.error('KAORI Report Templates configuration is invalid.', error)
            return null
        }
    }

    const config = parseConfig()
    if (!config) return

    const defaults = config.default_sections_by_report_type || {}
    const allowedFormats = config.allowed_formats_by_report_type || {}

    const initTemplateWorkspace = () => {
        const form = document.querySelector('[data-template-form]')
        if (!form || form.dataset.initialized === 'true') return

        const reportType = form.querySelector('[data-template-report-type]')
        const outputFormat = form.querySelector('[data-template-output-format]')
        const resetSections = form.querySelector('[data-template-reset-sections]')
        const sectionError = form.querySelector('[data-template-section-error]')
        if (!reportType || !outputFormat || !resetSections || !sectionError) return

        form.dataset.initialized = 'true'

        const sync = (reset = false) => {
            const selectedType = reportType.value
            const formats = allowedFormats[selectedType] || []
            Array.from(outputFormat.options).forEach((option) => {
                option.hidden = !formats.includes(option.value)
                option.disabled = !formats.includes(option.value)
            })
            if (!formats.includes(outputFormat.value)) outputFormat.value = formats[0] || ''

            form.querySelectorAll('[data-template-section-group]').forEach((group) => {
                const active = group.dataset.templateSectionGroup === selectedType
                group.classList.toggle('hidden', !active)
                group.querySelectorAll('input[name="sections"]').forEach((input) => {
                    input.disabled = !active
                    if (reset && active && input.type === 'checkbox') {
                        input.checked = (defaults[selectedType] || []).includes(input.value)
                    }
                })
            })
            sectionError.classList.add('hidden')
        }

        reportType.addEventListener('change', () => sync(true))
        resetSections.addEventListener('click', () => sync(true))
        form.addEventListener('submit', (event) => {
            sync(false)
            const activeGroup = form.querySelector(`[data-template-section-group="${reportType.value}"]`)
            if (
                activeGroup?.dataset.templateFamily !== 'inventory' &&
                !activeGroup?.querySelector('input[type="checkbox"]:checked')
            ) {
                event.preventDefault()
                sectionError.classList.remove('hidden')
                return
            }
        })
        sync(false)

        if (form.dataset.templateOpenFormDialog === 'true') {
            const dialog = document.getElementById('template-form-dialog')
            if (dialog && !dialog.open && typeof dialog.showModal === 'function') dialog.showModal()
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTemplateWorkspace, { once: true })
    } else {
        initTemplateWorkspace()
    }

    document.body.addEventListener('htmx:afterSwap', (event) => {
        initTemplateWorkspace()
        if (window.lucide && event.detail?.target?.id === 'templates-registry') window.lucide.createIcons()
    })
})()
