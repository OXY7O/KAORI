;(() => {
    const dialog = document.getElementById('kaori-session-expiry')
    if (!(dialog instanceof HTMLDialogElement)) return

    const { statusUrl, activityUrl, loginUrl, csrf } = dialog.dataset
    const countdown = dialog.querySelector('[data-session-expiry-countdown]')
    const description = dialog.querySelector('[data-session-expiry-description]')
    const message = dialog.querySelector('[data-session-expiry-message]')
    const continueButton = dialog.querySelector('[data-session-continue]')
    if (!statusUrl || !activityUrl || !loginUrl || !csrf || !countdown || !description || !message || !continueButton)
        return

    let idleDeadline = null
    let absoluteDeadline = null
    let warningSeconds = 120
    let statusPending = false
    let activityPending = false
    let lastActivityRequest = -Infinity
    let requestOrder = 0
    let appliedOrder = 0
    let unavailable = false
    let redirecting = false

    const signIn = () => {
        if (redirecting) return
        redirecting = true
        const target = new URL(loginUrl, window.location.origin)
        target.searchParams.set('next', window.location.pathname + window.location.search)
        window.location.replace(target.href)
    }

    const remaining = (deadline) => Math.max(0, Math.ceil((deadline - performance.now()) / 1000))
    const formatTime = (seconds) =>
        String(Math.floor(seconds / 60)).padStart(2, '0') + ':' + String(seconds % 60).padStart(2, '0')

    const render = () => {
        if (idleDeadline === null || absoluteDeadline === null || redirecting) return
        const idle = remaining(idleDeadline)
        const absolute = remaining(absoluteDeadline)
        const seconds = Math.min(idle, absolute)
        if (seconds > warningSeconds) {
            if (dialog.open) dialog.close()
            return
        }

        countdown.textContent = formatTime(seconds)
        const absoluteSoon = absolute <= warningSeconds
        description.textContent = absoluteSoon
            ? 'Your session is approaching its maximum authenticated age.'
            : 'Your session is approaching its inactivity deadline.'
        const notice = unavailable
            ? 'Unable to confirm session status. Retry or sign out.'
            : seconds === 0
              ? 'Checking the server deadline. Sign in again if the session has expired.'
              : absoluteSoon
                ? 'Maximum session age cannot be extended. Sign in again after expiry.'
                : 'Continuing can extend idle time only.'
        if (message.textContent !== notice) message.textContent = notice
        continueButton.disabled = activityPending || absoluteSoon || seconds === 0
        if (!dialog.open && document.visibilityState === 'visible') {
            dialog.showModal()
            window.renderKaoriIcons?.()
        }
    }

    const synchronize = async (activity = false) => {
        if (redirecting || (activity ? activityPending : statusPending)) return
        const order = ++requestOrder
        const startedAt = performance.now()
        if (activity) {
            activityPending = true
            lastActivityRequest = startedAt
        } else {
            statusPending = true
        }
        render()
        try {
            const response = await fetch(activity ? activityUrl : statusUrl, {
                method: activity ? 'POST' : 'GET',
                credentials: 'same-origin',
                cache: 'no-store',
                keepalive: activity,
                headers: activity ? { 'X-CSRFToken': csrf } : {},
            })
            if (response.status === 401) {
                signIn()
                return
            }
            if (!response.ok || response.redirected) throw new Error('Session state unavailable')
            const payload = await response.json()
            const values = [payload.idle_remaining_seconds, payload.absolute_remaining_seconds, payload.warning_seconds]
            if (!values.every((value) => Number.isFinite(value) && value >= 0)) {
                throw new Error('Invalid session deadline')
            }
            // A delayed passive response must not overwrite a newer activity
            // response. The client never adds time without an admitted server reply.
            if (order >= appliedOrder) {
                appliedOrder = order
                unavailable = false
                idleDeadline = startedAt + payload.idle_remaining_seconds * 1000
                absoluteDeadline = startedAt + payload.absolute_remaining_seconds * 1000
                warningSeconds = payload.warning_seconds
            }
        } catch {
            if (order >= appliedOrder) unavailable = true
        } finally {
            if (activity) activityPending = false
            else statusPending = false
            render()
        }
    }

    const deliberateActivity = (event) => {
        if (!event.isTrusted || document.visibilityState !== 'visible' || dialog.open || redirecting) return
        if (performance.now() - lastActivityRequest < 30000) return
        void synchronize(true)
    }

    for (const eventName of ['pointerdown', 'keydown', 'wheel', 'touchstart']) {
        document.addEventListener(eventName, deliberateActivity, { capture: true, passive: true })
    }
    continueButton.addEventListener('click', (event) => {
        if (event.isTrusted && !continueButton.disabled) void synchronize(true)
    })
    dialog.addEventListener('cancel', (event) => event.preventDefault())
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') void synchronize()
    })
    window.addEventListener('pageshow', () => void synchronize())
    window.setInterval(() => {
        if (document.visibilityState === 'visible') void synchronize()
    }, 15000)
    window.setInterval(render, 1000)
    void synchronize()
})()
