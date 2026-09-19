;(() => {
    const ROOT_SELECTOR = '[data-role-permission-editor]'

    function normalize(value) {
        return String(value || '')
            .trim()
            .toLowerCase()
    }

    function initializeRolePermissionEditor(root) {
        if (!(root instanceof HTMLElement) || root.dataset.rolePermissionEditorReady === 'true') {
            return
        }

        root.dataset.rolePermissionEditorReady = 'true'

        const searchInput = root.querySelector('[data-role-permission-search]')
        const selectedCount = root.querySelector('[data-role-selected-count]')
        const selectedModuleCount = root.querySelector('[data-role-selected-module-count]')
        const toggleAllButton = root.querySelector('[data-role-toggle-all]')
        const toggleAllLabel = root.querySelector('[data-role-toggle-all-label]')
        const moduleToggleAllButton = root.querySelector('[data-role-module-toggle-all]')
        const moduleToggleAllLabel = root.querySelector('[data-role-module-toggle-all-label]')
        const moduleSections = Array.from(root.querySelectorAll('[data-role-module-section]'))

        const permissionInputs = () => Array.from(root.querySelectorAll('[data-role-permission]'))

        function repairDocumentViewport() {
            if (window.scrollX !== 0 || window.scrollY !== 0) {
                window.scrollTo({ left: 0, top: 0, behavior: 'auto' })
            }
        }

        function moduleInputs(section) {
            return Array.from(section.querySelectorAll('[data-role-permission]'))
        }

        function visibleModuleSections() {
            return moduleSections.filter((section) => !section.hidden)
        }

        function syncModuleExpansionAction() {
            const visibleSections = visibleModuleSections()
            const allExpanded =
                visibleSections.length > 0 && visibleSections.every((section) => section.dataset.expanded === 'true')

            if (moduleToggleAllLabel) {
                moduleToggleAllLabel.textContent = allExpanded ? 'Collapse all' : 'Expand all'
            }
            if (moduleToggleAllButton) {
                moduleToggleAllButton.setAttribute('aria-pressed', allExpanded ? 'true' : 'false')
            }
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

            syncModuleExpansionAction()
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
            syncModuleExpansionAction()

            const editableInputs = permissionInputs().filter((input) => !input.disabled)
            const allSelected = editableInputs.length > 0 && editableInputs.every((input) => input.checked)
            if (toggleAllLabel) {
                toggleAllLabel.textContent = allSelected ? 'Clear all' : 'Select all'
            }
            if (toggleAllButton) {
                toggleAllButton.setAttribute('aria-pressed', allSelected ? 'true' : 'false')
            }
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

            syncModuleExpansionAction()
        }

        moduleSections.forEach((section) => {
            setModuleExpanded(section, false)

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

        moduleToggleAllButton?.addEventListener('click', () => {
            const sections = visibleModuleSections()
            const shouldExpand = sections.some((section) => section.dataset.expanded !== 'true')

            sections.forEach((section) => {
                setModuleExpanded(section, shouldExpand)
            })

            syncModuleExpansionAction()
        })

        toggleAllButton?.addEventListener('click', () => {
            const inputs = permissionInputs().filter((input) => !input.disabled)
            const shouldSelect = inputs.some((input) => !input.checked)

            inputs.forEach((input) => {
                input.checked = shouldSelect
            })

            syncSummary()
            requestAnimationFrame(repairDocumentViewport)
        })

        root.addEventListener('focusin', (event) => {
            if (event.target instanceof HTMLInputElement && event.target.matches('[data-role-permission]')) {
                requestAnimationFrame(repairDocumentViewport)
            }
        })

        root.addEventListener('change', (event) => {
            if (event.target instanceof HTMLInputElement && event.target.matches('[data-role-permission]')) {
                syncSummary()
                requestAnimationFrame(repairDocumentViewport)
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
