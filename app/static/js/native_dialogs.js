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

    const openDialog = (control) => {
        const dialog = resolveDialog(control)
        if (!dialog || dialog.open) return
        dialog.showModal()
        requestAnimationFrame(() => {
            const autofocus = dialog.querySelector('[autofocus]')
            const focusable = dialog.querySelector(
                'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )
            ;(autofocus || focusable)?.focus?.({ preventScroll: true })
            window.renderKaoriIcons?.()
        })
    }

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
