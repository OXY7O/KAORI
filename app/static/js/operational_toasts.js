;(() => {
    const toastSelector = '[data-operational-toast]'
    const stackSelector = '#operational-toast-stack'
    const maximumVisibleToasts = 4
    const reducedMotionQuery = '(prefers-reduced-motion: reduce)'
    const state = new WeakMap()

    const prefersReducedMotion = () => window.matchMedia?.(reducedMotionQuery)?.matches === true

    const cancelTimerVisual = (current) => {
        try {
            current?.animation?.cancel?.()
        } catch (_) {
            // Ignore stale browser animation handles.
        }
        if (current) current.animation = null
    }

    const dismiss = (toast) => {
        if (!(toast instanceof HTMLElement) || toast.dataset.toastDismissing === 'true') return
        toast.dataset.toastDismissing = 'true'
        const current = state.get(toast)
        if (current?.timer) window.clearTimeout(current.timer)
        cancelTimerVisual(current)
        toast.classList.add('opacity-0')
        if (prefersReducedMotion()) {
            toast.remove()
            return
        }
        window.setTimeout(() => toast.remove(), 200)
    }

    const runTimerVisual = (toast, current) => {
        const timerBar = toast.querySelector('[data-operational-toast-timer]')
        if (!(timerBar instanceof HTMLElement)) return

        const duration = Number(current.duration || toast.dataset.autoDismissMs || 0)
        const remaining = Math.max(0, Number(current.remaining || duration))
        const ratio = duration > 0 ? Math.max(0, Math.min(1, remaining / duration)) : 0

        cancelTimerVisual(current)
        timerBar.style.transformOrigin = 'left center'
        timerBar.style.transition = 'none'
        timerBar.style.transform = `scaleX(${ratio})`

        if (prefersReducedMotion()) {
            timerBar.style.transform = 'scaleX(1)'
            return
        }

        if (remaining <= 0) return

        if (typeof timerBar.animate === 'function') {
            current.animation = timerBar.animate([{ transform: `scaleX(${ratio})` }, { transform: 'scaleX(0)' }], {
                duration: remaining,
                easing: 'linear',
                fill: 'forwards',
            })
            return
        }

        // Fallback for browsers without Web Animations API. Force layout before
        // applying the transition so HTMX/OOB inserted toasts still animate.
        void timerBar.offsetWidth
        timerBar.style.transition = `transform ${remaining}ms linear`
        requestAnimationFrame(() => {
            timerBar.style.transform = 'scaleX(0)'
        })
    }

    const schedule = (toast, duration) => {
        if (!(toast instanceof HTMLElement) || duration <= 0) return
        const current = state.get(toast) || {
            duration,
            remaining: duration,
            timer: null,
            animation: null,
            startedAt: 0,
        }

        if (current.timer) window.clearTimeout(current.timer)
        current.duration = duration
        current.remaining = Math.max(0, current.remaining || duration)
        current.startedAt = performance.now()
        runTimerVisual(toast, current)
        current.timer = window.setTimeout(() => dismiss(toast), current.remaining)
        state.set(toast, current)
    }

    const pause = (toast) => {
        const current = state.get(toast)
        if (!current?.timer) return
        window.clearTimeout(current.timer)
        current.timer = null
        current.remaining = Math.max(0, current.remaining - (performance.now() - current.startedAt))
        current.animation?.pause?.()
    }

    const resume = (toast) => {
        const current = state.get(toast)
        if (!current || current.remaining <= 0) return
        schedule(toast, current.duration || Number(toast.dataset.autoDismissMs || 0))
    }

    const notifyActivityCenter = (element) => {
        if (!(element instanceof HTMLElement) || element.dataset.notificationRefreshDispatched === 'true') return
        element.dataset.notificationRefreshDispatched = 'true'
        document.body.dispatchEvent(new CustomEvent('kaori:notifications-changed', { bubbles: true }))
        if (!element.matches(toastSelector)) element.remove()
    }

    const enforceStackLimit = () => {
        const stack = document.querySelector(stackSelector)
        if (!stack) return
        const toasts = Array.from(stack.querySelectorAll(toastSelector))
        toasts.slice(0, Math.max(0, toasts.length - maximumVisibleToasts)).forEach(dismiss)
    }

    const initialiseToast = (toast) => {
        if (!(toast instanceof HTMLElement) || toast.dataset.toastInitialised === 'true') return
        toast.dataset.toastInitialised = 'true'

        const id = toast.dataset.toastId
        if (id) {
            document.querySelectorAll(`${toastSelector}[data-toast-id="${CSS.escape(id)}"]`).forEach((candidate) => {
                if (candidate !== toast) candidate.remove()
            })
        }

        toast.addEventListener('mouseenter', () => pause(toast))
        toast.addEventListener('mouseleave', () => resume(toast))
        toast.addEventListener('focusin', () => pause(toast))
        toast.addEventListener('focusout', () => resume(toast))

        if (prefersReducedMotion()) toast.classList.remove('opacity-0')
        else requestAnimationFrame(() => toast.classList.remove('opacity-0'))

        const duration = Number(toast.dataset.autoDismissMs || 0)
        if (duration > 0) {
            state.set(toast, {
                duration,
                remaining: duration,
                timer: null,
                animation: null,
                startedAt: 0,
            })
            schedule(toast, duration)
        }

        if (toast.matches('[data-operational-notification-refresh]')) notifyActivityCenter(toast)
        enforceStackLimit()
        window.renderKaoriIcons?.()
    }

    const initialise = (root = document) => {
        if (root.matches?.(toastSelector)) initialiseToast(root)
        root.querySelectorAll?.(toastSelector).forEach(initialiseToast)
        if (root.matches?.('[data-operational-notification-refresh]:not([data-operational-toast])')) {
            notifyActivityCenter(root)
        }
        root.querySelectorAll?.('[data-operational-notification-refresh]:not([data-operational-toast])').forEach(
            notifyActivityCenter
        )
    }

    document.addEventListener('click', (event) => {
        const target = event.target instanceof Element ? event.target : null
        const close = target?.closest('[data-operational-toast-close]')
        if (!close) return
        event.preventDefault()
        dismiss(close.closest(toastSelector))
    })

    document.addEventListener('htmx:load', (event) => initialise(event.detail?.elt || document))
    document.addEventListener('htmx:oobAfterSwap', (event) => initialise(event.detail?.target || document))

    window.dismissOperationalToast = (element) => dismiss(element?.closest?.(toastSelector) || element)

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => initialise())
    } else {
        initialise()
    }
})()
