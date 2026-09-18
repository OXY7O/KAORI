;(() => {
    'use strict'

    const detectedTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'

    const renderPreview = (previewClock, previewTimestamp, timezone) => {
        if (!previewClock) return

        try {
            previewClock.textContent = new Intl.DateTimeFormat(undefined, {
                timeZone: timezone,
                dateStyle: 'medium',
                timeStyle: 'medium',
            }).format(new Date(previewTimestamp))
        } catch (_) {
            previewClock.textContent = 'Invalid timezone'
        }
    }

    const initTimeLocaleWorkspace = (workspace) => {
        if (!workspace || workspace.dataset.timezoneRuntimeInitialized === 'true') return

        const modeInputs = workspace.querySelectorAll('input[name="timezone_mode"]')
        const manualPanel = workspace.querySelector('#manual-timezone-panel')
        const manualSelect = document.getElementById(workspace.dataset.timezoneManualSelect || '')
        const browserInput = document.getElementById(workspace.dataset.timezoneBrowserInput || '')
        const browserLabel = workspace.querySelector('#browser-timezone-label')
        const detectButton = workspace.querySelector('#detect-browser-timezone')
        const previewClock = document.getElementById('general-current-time')
        const previewTimestamp = workspace.dataset.timezonePreviewTimestamp || ''

        const selectedMode = () => workspace.querySelector('input[name="timezone_mode"]:checked')?.value

        const renderSelectedPreview = (timezone) => {
            renderPreview(previewClock, previewTimestamp, timezone)
        }

        const detect = () => {
            const timezone = detectedTimezone()
            if (browserInput) browserInput.value = timezone
            if (browserLabel) browserLabel.textContent = timezone
            if (selectedMode() === 'automatic') renderSelectedPreview(timezone)
        }

        const syncMode = () => {
            const automatic = selectedMode() === 'automatic'
            manualPanel?.classList.toggle('opacity-50', automatic)
            manualPanel?.classList.toggle('pointer-events-none', automatic)

            if (manualSelect) {
                manualSelect.tabIndex = automatic ? -1 : 0
                manualSelect.setAttribute('aria-disabled', automatic ? 'true' : 'false')
            }

            const timezone = automatic ? browserInput?.value || detectedTimezone() : manualSelect?.value || 'UTC'
            renderSelectedPreview(timezone)
        }

        workspace.dataset.timezoneRuntimeInitialized = 'true'

        modeInputs.forEach((input) => input.addEventListener('change', syncMode))
        manualSelect?.addEventListener('change', syncMode)
        detectButton?.addEventListener('click', () => {
            detect()
            syncMode()
        })

        detect()
        syncMode()
    }

    const initAllTimeLocaleWorkspaces = () => {
        document.querySelectorAll('[data-timezone-workspace]').forEach(initTimeLocaleWorkspace)
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllTimeLocaleWorkspaces, { once: true })
    } else {
        initAllTimeLocaleWorkspaces()
    }

    if (!window.kaoriTimeLocaleRuntimeBound) {
        window.kaoriTimeLocaleRuntimeBound = true
        document.body.addEventListener('htmx:afterSwap', initAllTimeLocaleWorkspaces)
    }
})()
