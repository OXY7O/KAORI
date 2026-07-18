(() => {
    const ROOT_SELECTOR = '[data-role-permission-editor]'

    function normalize(value) {
        return String(value || '').trim().toLowerCase()
    }

    function initializeRolePermissionEditor(root) {
        if (!(root instanceof HTMLElement) || root.dataset.rolePermissionEditorReady === 'true') {
            return
        }

        root.dataset.rolePermissionEditorReady = 'true'

        const searchInput = root.querySelector('[data-role-permission-search]')
        const selectedCount = root.querySelector('[data-role-selected-count]')
        const selectedModuleCount = root.querySelector('[data-role-selected-module-count]')
        const moduleSections = Array.from(root.querySelectorAll('[data-role-module-section]'))

        const permissionInputs = () => Array.from(root.querySelectorAll('[data-role-permission]'))

        function moduleInputs(section) {
            return Array.from(section.querySelectorAll('[data-role-permission]'))
        }

        function setModuleExpanded(section, expanded) {
            const content = section.querySelector('[data-role-module-content]')
            const chevrons = section.querySelectorAll('[data-role-module-chevron]')
            const toggles = section.querySelectorAll('[data-role-module-toggle]')

            section.dataset.expanded = expanded ? 'true' : 'false'

            if (content) {
                content.hidden = !expanded
            }

            chevrons.forEach((chevron) => {
                chevron.classList.toggle('rotate-180', expanded)
            })

            toggles.forEach((toggle) => {
                toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false')
            })
        }

        function syncModuleAction(section) {
            const inputs = moduleInputs(section).filter((input) => !input.disabled)
            const actionLabel = section.querySelector('[data-role-module-select-label]')
            const allSelected = inputs.length > 0 && inputs.every((input) => input.checked)

            if (actionLabel) {
                actionLabel.textContent = allSelected ? 'Clear module' : 'Select module'
            }
        }

        function syncSummary() {
            const checked = permissionInputs().filter((input) => input.checked)
            const modules = new Set(checked.map((input) => input.dataset.module).filter(Boolean))

            if (selectedCount) {
                selectedCount.textContent = String(checked.length)
            }

            if (selectedModuleCount) {
                selectedModuleCount.textContent = String(modules.size)
            }

            moduleSections.forEach(syncModuleAction)
        }

        function applySearch() {
            const term = normalize(searchInput?.value)

            moduleSections.forEach((section) => {
                const cards = Array.from(section.querySelectorAll('[data-role-permission-card]'))
                let visiblePermissionCount = 0

                cards.forEach((card) => {
                    const matches = !term || normalize(card.dataset.search).includes(term)
                    card.hidden = !matches
                    if (matches) {
                        visiblePermissionCount += 1
                    }
                })

                const sectionMatches = !term || normalize(section.dataset.search).includes(term)
                const visible = sectionMatches || visiblePermissionCount > 0
                section.hidden = !visible

                if (visible && term) {
                    setModuleExpanded(section, true)
                } else if (visible && !term) {
                    setModuleExpanded(section, section.dataset.expanded !== 'false')
                }
            })
        }

        moduleSections.forEach((section) => {
            setModuleExpanded(section, true)

            section.querySelectorAll('[data-role-module-toggle]').forEach((button) => {
                button.addEventListener('click', () => {
                    setModuleExpanded(section, section.dataset.expanded !== 'true')
                })
            })

            const selectButton = section.querySelector('[data-role-module-select]')
            if (selectButton) {
                selectButton.addEventListener('click', () => {
                    const inputs = moduleInputs(section).filter((input) => !input.disabled)
                    const shouldSelect = inputs.some((input) => !input.checked)

                    inputs.forEach((input) => {
                        input.checked = shouldSelect
                    })

                    syncSummary()
                })
            }
        })

        root.addEventListener('change', (event) => {
            if (event.target instanceof HTMLInputElement && event.target.matches('[data-role-permission]')) {
                syncSummary()
            }
        })

        searchInput?.addEventListener('input', applySearch)

        syncSummary()
        applySearch()
    }

    function initializeAll() {
        document.querySelectorAll(ROOT_SELECTOR).forEach(initializeRolePermissionEditor)
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeAll, { once: true })
    } else {
        initializeAll()
    }

    document.addEventListener('htmx:afterSwap', initializeAll)
})()
