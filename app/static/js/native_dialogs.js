;(() => {
    const openSelector = '[data-kaori-dialog-open]'
    const closeSelector = '[data-kaori-dialog-close]'
    const dialogSelector =
        'dialog[data-kaori-native-dialog], dialog[data-kaori-runtime-observation-dialog], dialog[data-kaori-binding-dialog]'

    const resolveDialog = (control) => {
        if (!(control instanceof HTMLElement)) return null
        const targetId = control.dataset.dialogTarget
        if (!targetId) return null
        const dialog = document.getElementById(targetId)
        return dialog instanceof HTMLDialogElement ? dialog : null
    }

    const showDialog = (dialog) => {
        if (!(dialog instanceof HTMLDialogElement) || dialog.open) return
        try {
            if (typeof dialog.showModal === 'function') dialog.showModal()
            else dialog.setAttribute('open', '')
        } catch {
            dialog.setAttribute('open', '')
        }
        requestAnimationFrame(() => {
            const autofocus = dialog.querySelector('[autofocus]')
            const focusable = dialog.querySelector(
                'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )
            ;(autofocus || focusable)?.focus?.({ preventScroll: true })
            window.renderKaoriIcons?.()
        })
    }

    const openDialog = (control) => showDialog(resolveDialog(control))

    // Workspace HTMX writes refresh committed evidence and append an OOB toast.
    // Only dialogs that opt into persistence are reopened after their owning
    // workspace is swapped; an explicit Close, Escape, or non-HTMX navigation
    // still dismisses them normally.
    let pendingDialogId = null
    document.addEventListener('htmx:beforeSwap', (event) => {
        const workspace = event.detail?.target || event.target
        if (!(workspace instanceof HTMLElement) || workspace.id !== 'tenant-admin-workspace')
            return
        const opened = workspace.querySelector(
            'dialog[data-kaori-native-dialog][data-kaori-dialog-preserve-on-swap][open]'
        )
        pendingDialogId = opened?.id || null
    })

    document.addEventListener('htmx:afterSwap', (event) => {
        const workspace = event.detail?.target || event.target
        if (!(workspace instanceof HTMLElement) || workspace.id !== 'tenant-admin-workspace')
            return
        const targetId = pendingDialogId
        pendingDialogId = null
        if (!targetId) return
        const nextDialog = document.getElementById(targetId)
        if (nextDialog instanceof HTMLDialogElement && nextDialog.matches('[data-kaori-dialog-preserve-on-swap]'))
            showDialog(nextDialog)
    })

    document.addEventListener('htmx:responseError', () => {
        pendingDialogId = null
    })

    const closeDialog = (control) => {
        if (!(control instanceof HTMLElement)) return
        const dialog = control.closest('dialog')
        if (dialog instanceof HTMLDialogElement && dialog.open) dialog.close()
    }

    document.addEventListener('click', (event) => {
        const target = event.target instanceof Element ? event.target : null
        if (!target) return

        const opener = target.closest(openSelector)
        if (opener) {
            event.preventDefault()
            openDialog(opener)
            return
        }

        const closer = target.closest(closeSelector)
        if (closer) {
            event.preventDefault()
            closeDialog(closer)
            return
        }

        const dialog = target.closest(dialogSelector)
        if (dialog instanceof HTMLDialogElement && event.target === dialog && dialog.open) {
            dialog.close()
        }
    })
})()
