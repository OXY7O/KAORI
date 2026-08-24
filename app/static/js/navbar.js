document.addEventListener('alpine:init', () => {
    window.Alpine.data('kaoriNavbar', () => ({
        quickOpen: false,
        searchOpen: false,
        searchQuery: '',
        searchSections: [],
        searchRecent: [],
        searchLoading: false,
        searchError: false,
        globalSearchSelectedId: null,
        globalSearchAbortController: null,
        globalSearchDebounceTimer: null,
        notificationDeckOpen: false,
        notificationDeckTab: 'notifications',
        notificationDeckSnapshotInFlight: false,
        notificationDeckSnapshotController: null,
        notificationDeckSnapshotQueued: false,
        notificationDeckAutoTimer: null,
        notificationDeckLastChecked: null,
        notificationDeckConnectionIssue: false,
        userOpen: false,
        aboutOpen: false,

        init() {
            this.loadGlobalSearchRecent()
            this.notificationDeckAutoTimer = window.setInterval(() => {
                this.queueNotificationDeckRefresh()
            }, 15000)
        },

        destroy() {
            window.clearInterval(this.notificationDeckAutoTimer)
            window.clearTimeout(this.globalSearchDebounceTimer)
            this.notificationDeckSnapshotController?.abort()
            this.globalSearchAbortController?.abort()
        },

        closeMenus() {
            this.quickOpen = false
            this.searchOpen = false
            this.notificationDeckOpen = false
            this.userOpen = false
            this.aboutOpen = false
            this.globalSearchAbortController?.abort()
        },

        toggleQuickActions() {
            this.quickOpen = !this.quickOpen
            this.searchOpen = false
            this.notificationDeckOpen = false
            this.userOpen = false
            this.aboutOpen = false
        },

        openNotificationDeck(tab = 'notifications') {
            this.notificationDeckTab = tab
            this.searchOpen = false
            this.notificationDeckOpen = true
            this.quickOpen = false
            this.userOpen = false
            this.aboutOpen = false
            this.queueNotificationDeckRefresh()
        },

        toggleUserMenu() {
            this.userOpen = !this.userOpen
            this.searchOpen = false
            this.quickOpen = false
            this.notificationDeckOpen = false
            this.aboutOpen = false
        },

        openAbout() {
            this.aboutOpen = true
            this.searchOpen = false
            this.quickOpen = false
            this.notificationDeckOpen = false
            this.userOpen = false
        },

        handleGlobalSearchShortcut(event) {
            const target = event.target
            const isEditable =
                target?.matches?.('input, textarea, select') || target?.isContentEditable === true
            const isCommandK = event.key?.toLowerCase() === 'k' && (event.ctrlKey || event.metaKey)
            const isSlash = event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !isEditable

            if (!isCommandK && !isSlash) return
            event.preventDefault()
            this.openGlobalSearch()
        },

        openGlobalSearch() {
            this.searchOpen = true
            this.quickOpen = false
            this.notificationDeckOpen = false
            this.userOpen = false
            this.aboutOpen = false
            this.runGlobalSearch()
            this.$nextTick?.(() => {
                document.querySelector('[data-global-search-input]')?.focus()
            })
        },

        closeGlobalSearch() {
            this.searchOpen = false
            this.searchLoading = false
            this.globalSearchSelectedId = null
            this.globalSearchAbortController?.abort()
            this.globalSearchAbortController = null
        },

        queueGlobalSearch() {
            window.clearTimeout(this.globalSearchDebounceTimer)
            this.globalSearchDebounceTimer = window.setTimeout(() => this.runGlobalSearch(), 180)
        },

        async runGlobalSearch() {
            const root = document.getElementById('global-search')
            const searchUrl = root?.dataset.searchUrl
            if (!searchUrl) return

            this.globalSearchAbortController?.abort()
            const controller = new AbortController()
            this.globalSearchAbortController = controller
            this.searchLoading = true
            this.searchError = false

            const url = new URL(searchUrl, window.location.origin)
            url.searchParams.set('q', this.searchQuery.trim())
            const currentClusterId = new URL(window.location.href).searchParams.get('cluster_id')
            if (currentClusterId) url.searchParams.set('cluster_id', currentClusterId)

            try {
                const response = await fetch(url.toString(), {
                    method: 'GET',
                    headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                    credentials: 'same-origin',
                    cache: 'no-store',
                    signal: controller.signal,
                })
                if (!response.ok) throw new Error(`Global search failed with HTTP ${response.status}.`)
                const payload = await response.json()
                this.searchSections = Array.isArray(payload.sections) ? payload.sections : []
                const items = this.globalSearchItems()
                this.globalSearchSelectedId = items[0]?.id || null
                this.$nextTick?.(() => window.renderKaoriIcons?.())
            } catch (error) {
                if (error?.name !== 'AbortError') {
                    this.searchSections = []
                    this.searchError = true
                    console.error('Global search failed.', error)
                }
            } finally {
                if (this.globalSearchAbortController === controller) {
                    this.globalSearchAbortController = null
                    this.searchLoading = false
                }
            }
        },

        globalSearchItems() {
            const recent = this.searchQuery.trim() ? [] : this.searchRecent
            const sectionItems = this.searchSections.flatMap((section) => section.items || [])
            return [...recent, ...sectionItems]
        },

        globalSearchHasResults() {
            return this.globalSearchItems().length > 0
        },

        setGlobalSearchSelection(item) {
            this.globalSearchSelectedId = item?.id || null
        },

        moveGlobalSearchSelection(direction) {
            const items = this.globalSearchItems()
            if (!items.length) return
            const currentIndex = items.findIndex((item) => item.id === this.globalSearchSelectedId)
            const nextIndex = currentIndex < 0
                ? 0
                : (currentIndex + direction + items.length) % items.length
            this.globalSearchSelectedId = items[nextIndex].id
            this.$nextTick?.(() => {
                document
                    .getElementById(`global-search-option-${this.globalSearchDomId(this.globalSearchSelectedId)}`)
                    ?.scrollIntoView({ block: 'nearest' })
            })
        },

        globalSearchDomId(value) {
            return String(value || '').replace(/[^a-zA-Z0-9_-]/g, '-')
        },

        trapGlobalSearchFocus(event) {
            const root = document.getElementById('global-search')
            if (!root) return
            const focusable = Array.from(
                root.querySelectorAll(
                    'button:not([disabled]), input:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
                )
            ).filter((element) => !element.hasAttribute('hidden') && element.offsetParent !== null)
            if (!focusable.length) return
            const first = focusable[0]
            const last = focusable[focusable.length - 1]
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault()
                last.focus()
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault()
                first.focus()
            }
        },

        openSelectedGlobalSearchResult() {
            const item = this.globalSearchItems().find((candidate) => candidate.id === this.globalSearchSelectedId)
            if (!item?.url) return
            this.rememberGlobalSearchResult(item)
            window.location.assign(item.url)
        },

        loadGlobalSearchRecent() {
            try {
                const stored = JSON.parse(window.localStorage?.getItem('kaori.globalSearch.recent') || '[]')
                this.searchRecent = Array.isArray(stored) ? stored.slice(0, 5) : []
            } catch (_error) {
                this.searchRecent = []
            }
        },

        rememberGlobalSearchResult(item) {
            if (!item?.id || !item?.url) return
            const recentItem = {
                id: item.id,
                kind: item.kind || 'Result',
                title: item.title || '',
                subtitle: item.subtitle || '',
                url: item.url,
                icon: item.icon || 'history',
            }
            this.searchRecent = [recentItem, ...this.searchRecent.filter((entry) => entry.id !== item.id)].slice(0, 5)
            try {
                window.localStorage?.setItem('kaori.globalSearch.recent', JSON.stringify(this.searchRecent))
            } catch (_error) {
                // Recent search history is optional and must not block navigation.
            }
        },

        clearGlobalSearchRecent() {
            this.searchRecent = []
            try {
                window.localStorage?.removeItem('kaori.globalSearch.recent')
            } catch (_error) {
                // Local history is optional.
            }
            const items = this.globalSearchItems()
            this.globalSearchSelectedId = items[0]?.id || null
        },

        globalSearchStatusClasses(tone) {
            if (tone === 'normal') return 'border-status-normal-border bg-status-normal-soft text-status-normal-text'
            if (tone === 'warning') return 'border-status-warning-border bg-status-warning-soft text-status-warning-text'
            if (tone === 'critical') return 'border-status-critical-border bg-status-critical-soft text-status-critical-text'
            if (tone === 'unknown') return 'border-status-unknown-border bg-status-unknown-soft text-status-unknown-text'
            return 'border-outline-default bg-surface-hover text-content-secondary'
        },

        applyNotificationDeckSnapshot(payload) {
            if (!payload || typeof payload !== 'object') {
                return
            }

            const activityTarget = document.getElementById('notification-deck-active-job-list')
            if (activityTarget && typeof payload.activity_html === 'string') {
                activityTarget.innerHTML = payload.activity_html
            }

            const inboxTarget = document.getElementById('notification-deck-inbox-content')
            if (inboxTarget && typeof payload.inbox_html === 'string') {
                inboxTarget.innerHTML = payload.inbox_html
                window.htmx?.process(inboxTarget)
            }

            const notificationsTarget = document.getElementById('notification-deck-notifications-content')
            if (notificationsTarget && typeof payload.notifications_html === 'string') {
                notificationsTarget.innerHTML = payload.notifications_html
                window.htmx?.process(notificationsTarget)
            }

            const activeCount = Number(payload.active_count || 0)
            const unreadCount = Number(payload.unread_count || 0)
            const inboxUnreadCount = Number(payload.inbox_unread_count || 0)
            const bellBadge = document.getElementById('notification-bell-badge')
            const inboxBadge = document.getElementById('work-inbox-badge')
            const runningIndicator = document.getElementById('notification-running-indicator')
            const activeBadge = document.getElementById('notification-deck-active-count')
            const inboxCountBadge = document.getElementById('notification-deck-inbox-count')
            const unreadBadge = document.getElementById('notification-deck-unread-count')

            if (bellBadge) {
                bellBadge.textContent = unreadCount > 9 ? '9+' : String(unreadCount)
                bellBadge.classList.toggle('hidden', unreadCount === 0)
            }

            if (inboxBadge) {
                inboxBadge.textContent = inboxUnreadCount > 9 ? '9+' : String(inboxUnreadCount)
                inboxBadge.classList.toggle('hidden', inboxUnreadCount === 0)
            }

            runningIndicator?.classList.toggle('hidden', activeCount === 0)

            if (activeBadge) {
                activeBadge.textContent = String(activeCount)
            }
            if (inboxCountBadge) {
                inboxCountBadge.textContent = String(inboxUnreadCount)
            }
            if (unreadBadge) {
                unreadBadge.textContent = String(unreadCount)
            }

            document.querySelectorAll('[data-activity-count-label]').forEach((label) => {
                label.textContent = String(activeCount)
            })

            window.renderLocalOperationalActivities?.()
            window.renderKaoriIcons?.()
        },

        queueNotificationDeckRefresh() {
            this.notificationDeckSnapshotQueued = true
            if (!this.notificationDeckSnapshotInFlight) {
                this.refreshNotificationDeck()
            }
        },

        async refreshNotificationDeck() {
            if (this.notificationDeckSnapshotInFlight) {
                this.notificationDeckSnapshotQueued = true
                return
            }

            this.notificationDeckSnapshotQueued = false

            const notificationCenter = document.getElementById('notification-center')
            const snapshotUrl = notificationCenter?.dataset.snapshotUrl
            if (!notificationCenter || !snapshotUrl) {
                this.notificationDeckConnectionIssue = true
                return
            }

            const controller = new AbortController()
            this.notificationDeckSnapshotInFlight = true
            this.notificationDeckSnapshotController = controller
            const timeoutId = window.setTimeout(() => controller.abort(), 5000)

            try {
                const response = await fetch(snapshotUrl, {
                    method: 'GET',
                    headers: {
                        Accept: 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    credentials: 'same-origin',
                    cache: 'no-store',
                    signal: controller.signal,
                })

                if (!response.ok) {
                    throw new Error(`Notification snapshot failed with HTTP ${response.status}.`)
                }

                const payload = await response.json()
                this.applyNotificationDeckSnapshot(payload)
                this.notificationDeckLastChecked = new Date().toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                })
                this.notificationDeckConnectionIssue = false
            } catch (error) {
                this.notificationDeckConnectionIssue = true
                if (error?.name !== 'AbortError') {
                    console.error('Notification snapshot refresh failed.', error)
                }
            } finally {
                window.clearTimeout(timeoutId)
                if (this.notificationDeckSnapshotController === controller) {
                    this.notificationDeckSnapshotController = null
                }
                this.notificationDeckSnapshotInFlight = false
                if (this.notificationDeckSnapshotQueued) {
                    window.queueMicrotask(() => this.refreshNotificationDeck())
                }
            }
        },
    }))
})
