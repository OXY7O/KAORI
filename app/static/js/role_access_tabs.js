(() => {
    const ROOT_SELECTOR = '[data-role-access-tabs]'
    const MATRIX_SELECTOR = '[data-role-matrix]'

    function initializeRoleAccessTabs(root) {
        if (!(root instanceof HTMLElement) || root.dataset.roleAccessTabsReady === 'true') {
            return
        }

        root.dataset.roleAccessTabsReady = 'true'
        const buttons = Array.from(root.querySelectorAll('[data-role-access-tab]'))
        const panels = Array.from(root.querySelectorAll('[data-role-access-panel]'))

        function activate(tabName, { updateHash = true } = {}) {
            const targetName = buttons.some((button) => button.dataset.roleAccessTab === tabName)
                ? tabName
                : 'registry'

            buttons.forEach((button) => {
                const active = button.dataset.roleAccessTab === targetName
                button.setAttribute('aria-selected', active ? 'true' : 'false')
                button.classList.toggle('bg-kaori-primary', active)
                button.classList.toggle('text-white', active)
                button.classList.toggle('text-content-secondary', !active)
                button.classList.toggle('hover:bg-surface-hover', !active)
                button.classList.toggle('hover:text-kaori-primary', !active)
            })

            panels.forEach((panel) => {
                panel.hidden = panel.dataset.roleAccessPanel !== targetName
            })

            if (updateHash) {
                const nextHash = targetName === 'matrix' ? '#role-permission-matrix' : '#role-registry'
                window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${nextHash}`)
            }

            if (window.renderKaoriIcons) {
                window.renderKaoriIcons()
            }
        }

        buttons.forEach((button) => {
            button.addEventListener('click', () => activate(button.dataset.roleAccessTab || 'registry'))
        })

        const initialTab = window.location.hash === '#role-permission-matrix' ? 'matrix' : 'registry'
        activate(initialTab, { updateHash: false })
    }

    function initializeRoleMatrix(root) {
        if (!(root instanceof HTMLElement) || root.dataset.roleMatrixReady === 'true') {
            return
        }

        root.dataset.roleMatrixReady = 'true'

        const roleHeaders = Array.from(root.querySelectorAll('[data-role-matrix-role]'))
        const roleCells = Array.from(root.querySelectorAll('[data-role-matrix-cell]'))
        const colspans = Array.from(root.querySelectorAll('[data-role-matrix-colspan]'))
        const searchInput = root.querySelector('[data-role-matrix-search]')
        const typeSelect = root.querySelector('[data-role-matrix-type]')
        const pageSizeSelect = root.querySelector('[data-role-matrix-page-size]')
        const previousButton = root.querySelector('[data-role-matrix-previous]')
        const nextButton = root.querySelector('[data-role-matrix-next]')
        const table = root.querySelector('[data-role-matrix-table]')
        const emptyState = root.querySelector('[data-role-matrix-empty]')
        const startOutput = root.querySelector('[data-role-matrix-start]')
        const endOutput = root.querySelector('[data-role-matrix-end]')
        const totalOutput = root.querySelector('[data-role-matrix-total]')
        const pageOutput = root.querySelector('[data-role-matrix-page]')
        const pagesOutput = root.querySelector('[data-role-matrix-pages]')

        let page = 1

        function filteredRoles() {
            const query = (searchInput?.value || '').trim().toLowerCase()
            const type = typeSelect?.value || 'all'

            return roleHeaders.filter((header) => {
                const queryMatch = !query || (header.dataset.roleSearch || '').includes(query)
                const typeMatch = type === 'all' || header.dataset.roleType === type
                return queryMatch && typeMatch
            })
        }

        function render() {
            const filtered = filteredRoles()
            const pageSize = Number(pageSizeSelect?.value || 5)
            const pages = Math.max(1, Math.ceil(filtered.length / pageSize))
            page = Math.min(page, pages)

            const startIndex = (page - 1) * pageSize
            const visibleRoles = filtered.slice(startIndex, startIndex + pageSize)
            const visibleRoleIds = new Set(visibleRoles.map((header) => header.dataset.roleId))

            roleHeaders.forEach((header) => {
                header.hidden = !visibleRoleIds.has(header.dataset.roleId)
            })

            roleCells.forEach((cell) => {
                cell.hidden = !visibleRoleIds.has(cell.dataset.roleId)
            })

            colspans.forEach((cell) => {
                cell.colSpan = Math.max(1, visibleRoles.length + 1)
            })

            const hasRoles = filtered.length > 0
            if (table instanceof HTMLElement) {
                table.hidden = !hasRoles
            }
            if (emptyState instanceof HTMLElement) {
                emptyState.hidden = hasRoles
            }

            const visibleStart = hasRoles ? startIndex + 1 : 0
            const visibleEnd = hasRoles ? Math.min(startIndex + pageSize, filtered.length) : 0

            if (startOutput) startOutput.textContent = String(visibleStart)
            if (endOutput) endOutput.textContent = String(visibleEnd)
            if (totalOutput) totalOutput.textContent = String(filtered.length)
            if (pageOutput) pageOutput.textContent = String(page)
            if (pagesOutput) pagesOutput.textContent = String(pages)

            if (previousButton instanceof HTMLButtonElement) {
                previousButton.disabled = !hasRoles || page <= 1
            }
            if (nextButton instanceof HTMLButtonElement) {
                nextButton.disabled = !hasRoles || page >= pages
            }

            if (window.renderKaoriIcons) {
                window.renderKaoriIcons()
            }
        }

        searchInput?.addEventListener('input', () => {
            page = 1
            render()
        })
        typeSelect?.addEventListener('change', () => {
            page = 1
            render()
        })
        pageSizeSelect?.addEventListener('change', () => {
            page = 1
            render()
        })
        previousButton?.addEventListener('click', () => {
            page = Math.max(1, page - 1)
            render()
        })
        nextButton?.addEventListener('click', () => {
            page += 1
            render()
        })

        render()
    }

    function initializeAll() {
        document.querySelectorAll(ROOT_SELECTOR).forEach(initializeRoleAccessTabs)
        document.querySelectorAll(MATRIX_SELECTOR).forEach(initializeRoleMatrix)
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeAll, { once: true })
    } else {
        initializeAll()
    }

    document.addEventListener('htmx:afterSwap', initializeAll)
})()
