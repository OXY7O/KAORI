document.addEventListener('alpine:init', () => {
    window.Alpine.data('kaoriSideDrawer', () => ({
        open: false,
        opener: null,
        dialog: null,
        keydownHandler: null,

        init() {
            this.keydownHandler = (event) => {
                if (!this.open || event.key !== 'Tab') return
                this.trapFocus(event, this.dialog)
            }
            document.addEventListener('keydown', this.keydownHandler)
        },

        destroy() {
            if (this.keydownHandler) document.removeEventListener('keydown', this.keydownHandler)
        },

        currentFocusTarget() {
            const target = document.activeElement
            return target && typeof target.focus === 'function' ? target : null
        },

        focusableElements(dialog) {
            if (!dialog || typeof dialog.querySelectorAll !== 'function') return []
            return Array.from(
                dialog.querySelectorAll(
                    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
                )
            ).filter((element) => !element.hasAttribute('hidden') && element.offsetParent !== null)
        },

        focusDialog(dialog) {
            this.$nextTick?.(() => {
                if (!this.open || !dialog) return
                const focusables = this.focusableElements(dialog)
                const target = focusables[0] || dialog
                if (typeof target.focus === 'function') target.focus()
            })
        },

        restoreFocus(target) {
            this.$nextTick?.(() => {
                if (!target || typeof target.focus !== 'function') return
                const isConnected = typeof document.contains !== 'function' || document.contains(target)
                if (target.offsetParent !== null && isConnected) target.focus()
            })
        },

        syncOpen(isOpen, dialog) {
            const nextOpen = Boolean(isOpen)
            if (nextOpen === this.open) {
                if (nextOpen) this.dialog = dialog
                return
            }

            if (nextOpen) {
                this.opener = this.currentFocusTarget()
                this.dialog = dialog
                this.open = true
                this.focusDialog(dialog)
                return
            }

            const returnTarget = this.opener
            this.open = false
            this.dialog = null
            this.opener = null
            this.restoreFocus(returnTarget)
        },

        trapFocus(event, dialog) {
            const focusables = this.focusableElements(dialog)
            if (!focusables.length) {
                event.preventDefault()
                dialog?.focus()
                return
            }

            const first = focusables[0]
            const last = focusables[focusables.length - 1]
            if (!dialog.contains(document.activeElement)) {
                event.preventDefault()
                first.focus()
                return
            }
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault()
                last.focus()
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault()
                first.focus()
            }
        },
    }))
})
