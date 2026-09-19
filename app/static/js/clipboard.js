;(() => {
    const copyTimers = new WeakMap()

    const renderIcons = () => {
        if (typeof window.renderKaoriIcons === 'function') {
            window.renderKaoriIcons()
            return
        }
        if (window.lucide) {
            window.lucide.createIcons()
        }
    }

    const fallbackCopy = (text) => {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.setAttribute('readonly', '')
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        textarea.style.pointerEvents = 'none'
        document.body.appendChild(textarea)
        textarea.select()

        let copied = false
        try {
            copied = document.execCommand('copy')
        } finally {
            textarea.remove()
        }
        return copied
    }

    const copyText = async (text) => {
        if (navigator.clipboard?.writeText) {
            try {
                await navigator.clipboard.writeText(text)
                return true
            } catch (_error) {
                // Fall through for browsers or contexts that deny Clipboard API access.
            }
        }
        return fallbackCopy(text)
    }

    const setCopyState = (button, copied) => {
        const label = button.querySelector('[data-kaori-copy-label]')
        const icon = button.querySelector('[data-kaori-copy-icon]')
        const defaultLabel = button.dataset.copyLabel || 'Copy'
        const copiedLabel = button.dataset.copiedLabel || 'Copied'

        if (label) {
            label.textContent = copied ? copiedLabel : defaultLabel
        }
        if (icon) {
            icon.setAttribute('data-lucide', copied ? 'check' : 'copy')
            renderIcons()
        }
    }

    document.addEventListener('click', async (event) => {
        const button = event.target.closest('[data-kaori-copy-button]')
        if (!button) {
            return
        }

        const root = button.closest('[data-kaori-copy-root]')
        const source = root?.querySelector('[data-kaori-copy-source]')
        const text = source?.textContent?.trim()
        if (!text) {
            return
        }

        const copied = await copyText(text)
        if (!copied) {
            return
        }

        const currentTimer = copyTimers.get(button)
        if (currentTimer) {
            window.clearTimeout(currentTimer)
        }

        setCopyState(button, true)
        const timer = window.setTimeout(() => {
            setCopyState(button, false)
            copyTimers.delete(button)
        }, 1600)
        copyTimers.set(button, timer)
    })
})()
