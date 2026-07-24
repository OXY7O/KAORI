;(function () {
    const initializeWorkspaceCatalog = () => {
        const catalog = document.querySelector('[data-workspace-catalog]')
        const searchInput = catalog?.querySelector('[data-workspace-search]')
        const cards = Array.from(catalog?.querySelectorAll('[data-workspace-card]') || [])
        const groups = Array.from(catalog?.querySelectorAll('[data-workspace-group]') || [])
        const resultCount = catalog?.querySelector('[data-workspace-result-count]')
        const emptyState = catalog?.querySelector('[data-workspace-empty]')

        if (!catalog || !searchInput) {
            return
        }

        const updateResults = () => {
            const query = searchInput.value.trim().toLowerCase()
            let visibleCardCount = 0

            cards.forEach((card) => {
                const matches = !query || (card.dataset.searchText || '').includes(query)
                card.hidden = !matches

                if (matches) {
                    visibleCardCount += 1
                }
            })

            groups.forEach((group) => {
                const groupCards = Array.from(group.querySelectorAll('[data-workspace-card]'))
                const visibleGroupCards = groupCards.filter((card) => !card.hidden)
                const groupResultCount = group.querySelector('[data-group-result-count]')

                group.hidden = visibleGroupCards.length === 0
                group.open = Boolean(query) && visibleGroupCards.length > 0

                if (groupResultCount) {
                    groupResultCount.textContent = String(visibleGroupCards.length)
                }
            })

            if (resultCount) {
                const noun = visibleCardCount === 1 ? 'Workspace' : 'Workspaces'
                resultCount.textContent = `${visibleCardCount} ${noun} Available`
            }

            if (emptyState) {
                emptyState.hidden = visibleCardCount !== 0
            }
        }

        searchInput.addEventListener('input', updateResults)

        document.addEventListener('keydown', (event) => {
            const activeElement = document.activeElement
            const editingText = activeElement instanceof HTMLInputElement ||
                activeElement instanceof HTMLTextAreaElement ||
                activeElement?.isContentEditable

            if (event.key === '/' && !editingText) {
                event.preventDefault()
                searchInput.focus()
            }

            if (event.key === 'Escape' && activeElement === searchInput) {
                searchInput.value = ''
                updateResults()
                searchInput.blur()
            }
        })
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeWorkspaceCatalog)
    } else {
        initializeWorkspaceCatalog()
    }
})()
