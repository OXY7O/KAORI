;(function () {
    'use strict'

    window.integrationWorkspaceTabs = function integrationWorkspaceTabs(
        tabs,
        defaultTab = 'configuration',
        workspaceId = null
    ) {
        const allowedTabs = Array.isArray(tabs) ? tabs : []

        const resolveTab = () => {
            const url = new URL(window.location.href)
            const queryTab = url.searchParams.get('tab')
            const hashTab = window.location.hash.replace('#', '')
            if (allowedTabs.includes(queryTab)) return queryTab
            if (allowedTabs.includes(hashTab)) return hashTab
            return allowedTabs.includes(defaultTab) ? defaultTab : allowedTabs[0]
        }

        return {
            tabs: allowedTabs,
            activeTab: resolveTab(),
            setTab(tab, moveToWorkspace = false) {
                if (!this.tabs.includes(tab)) return
                this.activeTab = tab
                const nextUrl = new URL(window.location.href)
                nextUrl.searchParams.set('tab', tab)
                nextUrl.hash = tab
                window.history.replaceState(null, '', nextUrl)
                if (moveToWorkspace && workspaceId) {
                    this.$nextTick(() =>
                        document.getElementById(workspaceId)?.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start',
                        })
                    )
                }
            },
            moveTab(currentTab, direction, prefix = 'integration') {
                const currentIndex = this.tabs.indexOf(currentTab)
                if (currentIndex < 0) return
                let nextIndex = currentIndex
                if (direction === 'home') nextIndex = 0
                else if (direction === 'end') nextIndex = this.tabs.length - 1
                else nextIndex = (currentIndex + direction + this.tabs.length) % this.tabs.length
                const nextTab = this.tabs[nextIndex]
                this.setTab(nextTab)
                this.$nextTick(() => document.getElementById(`${prefix}-tab-${nextTab}`)?.focus())
            },
            syncTab() {
                this.activeTab = resolveTab()
            },
        }
    }
})()
