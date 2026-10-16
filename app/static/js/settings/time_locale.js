;(() => {
    'use strict'

    const detectedTimezone = () => {
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
        if (typeof timezone !== 'string' || !timezone.trim()) {
            throw new Error('Browser timezone unavailable')
        }
        return timezone
    }

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

        const notifyDetection = (status, message) => {
            const template = workspace.querySelector(`template[data-timezone-detection-toast="${status}"]`)
            const toast = template?.content?.firstElementChild?.cloneNode(true)
            if (!(toast instanceof HTMLElement)) return

            const messageNode = toast.querySelector('[data-operational-toast-message]')
            if (messageNode) messageNode.textContent = message
            window.showOperationalToast?.(toast)
        }

        const selectedMode = () => workspace.querySelector('input[name="timezone_mode"]:checked')?.value

        const renderSelectedPreview = (timezone) => {
            renderPreview(previewClock, previewTimestamp, timezone)
        }

        const detect = () => {
            let timezone
            try {
                timezone = detectedTimezone()
            } catch (_) {
                if (browserLabel && browserLabel.textContent === 'Detecting…') {
                    browserLabel.textContent = 'Unavailable'
                }
                return null
            }
            if (browserInput) browserInput.value = timezone
            if (browserLabel) browserLabel.textContent = timezone
            if (selectedMode() === 'automatic') renderSelectedPreview(timezone)
            return timezone
        }

        const syncMode = () => {
            const automatic = selectedMode() === 'automatic'
            manualPanel?.classList.toggle('opacity-50', automatic)
            manualPanel?.classList.toggle('pointer-events-none', automatic)

            if (manualSelect) {
                manualSelect.tabIndex = automatic ? -1 : 0
                manualSelect.setAttribute('aria-disabled', automatic ? 'true' : 'false')
            }

            const timezone = automatic ? browserInput?.value || 'UTC' : manualSelect?.value || 'UTC'
            renderSelectedPreview(timezone)
        }

        workspace.dataset.timezoneRuntimeInitialized = 'true'

        modeInputs.forEach((input) => input.addEventListener('change', syncMode))
        manualSelect?.addEventListener('change', syncMode)
        detectButton?.addEventListener('click', () => {
            const previousTimezone = browserInput?.value || ''
            const timezone = detect()
            if (!timezone) {
                notifyDetection(
                    'error',
                    'Unable to detect browser time zone. The previously detected value is unchanged; no preference was saved.'
                )
                return
            }

            syncMode()
            const unchanged = timezone === previousTimezone
            notifyDetection(
                'success',
                unchanged
                    ? `Browser time zone is unchanged (${timezone}). No preference was saved.`
                    : `Detected browser time zone: ${timezone}. No preference was saved.`
            )
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
