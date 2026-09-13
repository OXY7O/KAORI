document.addEventListener('DOMContentLoaded', () => {
    const focusableSelector = [
        'button:not([disabled])',
        '[href]',
        'input:not([disabled])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])',
    ].join(',')

    const isVisible = (element) => element instanceof HTMLElement && element.offsetParent !== null
    const userMenuTrigger = () => document.querySelector('button[aria-label="Open user menu"]')
    const globalSearchRoot = () => document.getElementById('global-search')
    const globalSearchDialog = () => globalSearchRoot()?.querySelector('[role="dialog"]')
    const aboutDialog = () => document.getElementById('kaori-about-dialog')

    const focusableElements = (dialog) => {
        if (!(dialog instanceof HTMLElement)) return []
        return Array.from(dialog.querySelectorAll(focusableSelector)).filter(isVisible)
    }

    const trapFocus = (dialog, event) => {
        if (!(dialog instanceof HTMLElement)) return
        const focusable = focusableElements(dialog)
        if (!focusable.length) {
            event.preventDefault()
            dialog.focus()
            return
        }

        const active = document.activeElement
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (!dialog.contains(active)) {
            event.preventDefault()
            first.focus()
        } else if (event.shiftKey && (active === first || active === dialog)) {
            event.preventDefault()
            last.focus()
        } else if (!event.shiftKey && active === last) {
            event.preventDefault()
            first.focus()
        }
    }

    const restoreFocus = (target) => {
        window.setTimeout(() => {
            if (isVisible(target) && document.contains(target)) target.focus()
        }, 0)
    }

    const quickActionTriggers = Array.from(document.querySelectorAll('button[aria-label="Open quick actions"]'))
    const quickActionsMenu = quickActionTriggers[0]?.parentElement?.querySelector('[x-show="quickOpen"]')
    if (quickActionsMenu instanceof HTMLElement) {
        quickActionsMenu.id = 'quick-actions-menu'
        quickActionTriggers.forEach((trigger) => trigger.setAttribute('aria-controls', quickActionsMenu.id))
    }

    const globalSearchTriggers = Array.from(document.querySelectorAll('button[aria-label="Open global search"]'))
    globalSearchTriggers.forEach((trigger) => trigger.setAttribute('aria-controls', 'global-search'))

    let quickActionsTrigger = null
    let globalSearchReturnTarget = null

    document.addEventListener(
        'click',
        (event) => {
            const target = event.target instanceof Element ? event.target : null
            const button = target?.closest('button')
            if (!(button instanceof HTMLElement)) return

            if (quickActionTriggers.includes(button)) {
                quickActionsTrigger = button
                return
            }

            if (globalSearchTriggers.includes(button)) {
                globalSearchReturnTarget = button
                return
            }

            if (button.getAttribute('@click')?.includes('openAbout')) {
                window.setTimeout(() => aboutDialog()?.focus(), 0)
                return
            }

            if (button.getAttribute('aria-label') === 'Close global search') {
                restoreFocus(globalSearchReturnTarget)
                return
            }

            const dialog = aboutDialog()
            const closesAbout =
                button.getAttribute('aria-label') === 'Close About KAORI' ||
                (dialog?.contains(button) && button.textContent?.trim() === 'Close')
            if (closesAbout) restoreFocus(userMenuTrigger())
        },
        true
    )

    document.addEventListener(
        'keydown',
        (event) => {
            const about = aboutDialog()
            const search = globalSearchDialog()

            if (event.key === 'Tab') {
                if (isVisible(about)) {
                    trapFocus(about, event)
                    return
                }
                if (isVisible(search)) trapFocus(search, event)
                return
            }

            if (event.key === 'Escape') {
                if (isVisible(about)) {
                    restoreFocus(userMenuTrigger())
                    return
                }
                if (isVisible(search)) {
                    restoreFocus(globalSearchReturnTarget)
                    return
                }
                if (isVisible(quickActionsMenu)) restoreFocus(quickActionsTrigger)
                return
            }

            const target = event.target
            const editable = target?.matches?.('input, textarea, select') || target?.isContentEditable === true
            const commandK = event.key?.toLowerCase() === 'k' && (event.ctrlKey || event.metaKey)
            const slash = event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !editable
            if (commandK || slash) {
                globalSearchReturnTarget = document.activeElement instanceof HTMLElement ? document.activeElement : null
            }
        },
        true
    )
})
