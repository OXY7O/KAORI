document.addEventListener('alpine:init', () => {
    window.Alpine.data('kaoriNavbar', () => ({
        quickOpen: false,
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
            this.notificationDeckAutoTimer = window.setInterval(() => {
                this.queueNotificationDeckRefresh()
            }, 15000)
        },

        destroy() {
            window.clearInterval(this.notificationDeckAutoTimer)
            this.notificationDeckSnapshotController?.abort()
        },

        closeMenus() {
            this.quickOpen = false
            this.notificationDeckOpen = false
            this.userOpen = false
            this.aboutOpen = false
        },

        toggleQuickActions() {
            this.quickOpen = !this.quickOpen
            this.notificationDeckOpen = false
            this.userOpen = false
            this.aboutOpen = false
        },

        openNotificationDeck(tab = 'notifications') {
            this.notificationDeckTab = tab
            this.notificationDeckOpen = true
            this.quickOpen = false
            this.userOpen = false
            this.aboutOpen = false
            this.queueNotificationDeckRefresh()
        },

        toggleUserMenu() {
            this.userOpen = !this.userOpen
            this.quickOpen = false
            this.notificationDeckOpen = false
            this.aboutOpen = false
        },

        openAbout() {
            this.aboutOpen = true
            this.quickOpen = false
            this.notificationDeckOpen = false
            this.userOpen = false
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
