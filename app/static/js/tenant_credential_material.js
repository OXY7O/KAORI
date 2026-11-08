;(() => {
    const formatDuration = (seconds) => {
        const value = Number(seconds || 0)
        if (value >= 3600) {
            const hours = value / 3600
            return `${hours} hour${hours === 1 ? '' : 's'}`
        }
        const minutes = Math.round(value / 60)
        return `${minutes} minute${minutes === 1 ? '' : 's'}`
    }

    const updateLifetimePolicy = (namespaceSelect) => {
        const dialog = namespaceSelect.closest('dialog')
        if (!dialog) {
            return
        }

        const ttlSelect = dialog.querySelector('[data-credential-material-ttl]')
        const policyText = dialog.querySelector('[data-credential-material-policy]')
        const selected = namespaceSelect.selectedOptions?.[0]
        if (!ttlSelect || !selected) {
            return
        }

        const maxSeconds = Number(selected.dataset.maxTtl || 3600)
        const defaultSeconds = Number(selected.dataset.defaultTtl || Math.min(3600, maxSeconds))
        const environment = selected.dataset.environment || 'target'

        let selectedAllowed = false
        for (const option of ttlSelect.options) {
            const seconds = Number(option.value || 0)
            const allowed = seconds > 0 && seconds <= maxSeconds
            option.disabled = !allowed
            option.hidden = !allowed
            if (option.selected && allowed) {
                selectedAllowed = true
            }
        }

        if (!selectedAllowed) {
            const preferred = Array.from(ttlSelect.options).find(
                (option) => Number(option.value) === defaultSeconds && !option.disabled
            )
            const fallback = Array.from(ttlSelect.options)
                .filter((option) => !option.disabled)
                .at(-1)
            ;(preferred || fallback)?.setAttribute('selected', 'selected')
            if (preferred || fallback) {
                ttlSelect.value = (preferred || fallback).value
            }
        }

        if (policyText) {
            policyText.textContent = `${environment.charAt(0).toUpperCase() + environment.slice(1)} policy allows up to ${formatDuration(maxSeconds)} per generation. Kubernetes may return a shorter actual expiry.`
        }
    }

    const initialize = (root = document) => {
        root.querySelectorAll('[data-credential-material-namespace]').forEach(updateLifetimePolicy)
    }

    document.addEventListener('change', (event) => {
        const namespaceSelect = event.target.closest('[data-credential-material-namespace]')
        if (namespaceSelect) {
            updateLifetimePolicy(namespaceSelect)
        }
    })

    document.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-credential-material-open]')
        if (!trigger) {
            return
        }
        const dialogId = trigger.dataset.dialogTarget
        if (!dialogId) {
            return
        }
        window.setTimeout(() => {
            const dialog = document.getElementById(dialogId)
            const namespaceSelect = dialog?.querySelector('[data-credential-material-namespace]')
            if (namespaceSelect) {
                updateLifetimePolicy(namespaceSelect)
            }
        }, 0)
    })

    document.addEventListener('DOMContentLoaded', () => initialize())
    document.addEventListener('htmx:afterSwap', (event) => initialize(event.target))

    window.addEventListener('pagehide', () => {
        document.querySelectorAll('[data-kaori-sensitive-material]').forEach((node) => {
            node.textContent = ''
        })
    })
})()
