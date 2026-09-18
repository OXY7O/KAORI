window.renderKaoriIcons = () => {
    const renderTextFallback = (icons) => {
        icons.forEach((icon) => {
            icon.removeAttribute('data-lucide')
            icon.setAttribute('aria-hidden', 'true')
            icon.classList.add('inline-flex', 'items-center', 'justify-center')
            icon.textContent = '•'
        })
    }

    if (!window.lucide) {
        renderTextFallback(document.querySelectorAll('i[data-lucide]'))
        return
    }

    try {
        window.lucide.createIcons()
    } catch (error) {
        console.warn('Lucide icon rendering failed.', error)
    }

    const unresolvedIcons = document.querySelectorAll('i[data-lucide]')
    if (!unresolvedIcons.length) {
        return
    }

    unresolvedIcons.forEach((icon) => {
        console.warn(`Unsupported Lucide icon: ${icon.dataset.lucide}`)
        icon.dataset.lucide = 'circle'
    })

    try {
        window.lucide.createIcons()
    } catch (error) {
        console.warn('Lucide fallback icon rendering failed.', error)
    }

    const stillUnresolvedIcons = document.querySelectorAll('i[data-lucide]')
    if (stillUnresolvedIcons.length) {
        renderTextFallback(stillUnresolvedIcons)
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.renderKaoriIcons()
    window.renderLocalOperationalActivities?.()
})

document.body.addEventListener('htmx:afterSwap', (event) => {
    if (window.Alpine && event.detail && event.detail.elt) {
        window.Alpine.initTree(event.detail.elt)
    }

    window.renderKaoriIcons()
    window.renderLocalOperationalActivities?.()
})

const localOperationalActivities = new Map()
const operationalActivityByRequest = new WeakMap()
const operationalRefreshInFlight = new Map()

const buildLocalActivityNode = (activity) => {
    const card = document.createElement('article')
    card.className = 'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-3 shadow-sm'
    card.setAttribute('data-local-activity-id', activity.id)

    const row = document.createElement('div')
    row.className = 'flex items-start gap-3'

    const icon = document.createElement('span')
    icon.className = 'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-kaori-primary text-white'
    icon.innerHTML = '<i data-lucide="loader-circle" class="h-4 w-4 animate-spin"></i>'

    const copy = document.createElement('div')
    copy.className = 'min-w-0 flex-1'

    const header = document.createElement('div')
    header.className = 'flex items-start justify-between gap-3'

    const title = document.createElement('p')
    title.className = 'truncate text-xs font-semibold text-content-primary'
    title.textContent = activity.title

    const state = document.createElement('span')
    state.className =
        'inline-flex min-h-6 shrink-0 items-center rounded-md bg-surface-card px-2 py-1 text-xs font-semibold text-kaori-primary'
    state.textContent = 'In progress'

    const message = document.createElement('p')
    message.className = 'mt-1 text-xs leading-5 text-content-secondary'
    message.textContent = activity.message

    const progress = document.createElement('div')
    progress.className = 'mt-3 h-1.5 overflow-hidden rounded-full bg-surface-card'
    progress.innerHTML = '<div class="notification-progress-indeterminate h-full rounded-full bg-kaori-primary"></div>'

    header.append(title, state)
    copy.append(header, message, progress)
    row.append(icon, copy)
    card.append(row)
    return card
}

window.renderLocalOperationalActivities = () => {
    const localNodes = Array.from(localOperationalActivities.values(), buildLocalActivityNode)
    let indicatorCount = localOperationalActivities.size

    document.querySelectorAll('[data-activity-surface]').forEach((surface) => {
        const serverCount = surface.querySelectorAll('[data-server-activity-item]').length
        const totalCount = serverCount + localOperationalActivities.size
        indicatorCount = Math.max(indicatorCount, totalCount)

        surface.querySelectorAll('[data-local-activity-list]').forEach((list) => {
            list.replaceChildren(...localNodes.map((node) => node.cloneNode(true)))
        })

        surface.querySelectorAll('[data-activity-count-label]').forEach((label) => {
            label.textContent = String(totalCount)
        })

        surface.querySelectorAll('[data-running-empty]').forEach((emptyState) => {
            emptyState.classList.toggle('hidden', totalCount > 0)
        })
    })

    const runningIndicator = document.getElementById('notification-running-indicator')
    runningIndicator?.classList.toggle('hidden', indicatorCount === 0)

    const activeCountBadge = document.getElementById('notification-deck-active-count')
    if (activeCountBadge) {
        activeCountBadge.textContent = String(indicatorCount)
    }

    window.renderKaoriIcons?.()
}

window.startOperationalActivity = (title, message) => {
    const activityId = `local-activity-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    localOperationalActivities.set(activityId, {
        id: activityId,
        title: title || 'Operation in progress',
        message: message || 'KAORI is processing the requested operation.',
    })
    window.renderLocalOperationalActivities()
    return activityId
}

window.finishOperationalActivity = (activityId) => {
    if (!activityId) {
        return
    }
    localOperationalActivities.delete(activityId)
    window.renderLocalOperationalActivities()
}

window.refreshOperationalTable = async (url) => {
    if (!url) {
        return
    }

    const targetSelector = '#cluster-table-container'
    const currentTarget = document.querySelector(targetSelector)

    if (!currentTarget) {
        return
    }

    const previousController = operationalRefreshInFlight.get(targetSelector)
    if (previousController) {
        previousController.abort()
    }

    const controller = new AbortController()
    operationalRefreshInFlight.set(targetSelector, controller)

    try {
        const response = await fetch(url, {
            headers: {
                'HX-Request': 'true',
                'X-KAORI-Operational-Refresh': 'true',
            },
            signal: controller.signal,
            credentials: 'same-origin',
        })

        if (!response.ok) {
            return
        }

        const html = await response.text()
        const template = document.createElement('template')
        template.innerHTML = html.trim()
        const replacement = template.content.querySelector(targetSelector)
        const liveTarget = document.querySelector(targetSelector)

        if (!replacement || !liveTarget) {
            return
        }

        liveTarget.replaceWith(replacement)
        window.htmx?.process(replacement)
        window.lucide?.createIcons()
    } catch (error) {
        if (error?.name !== 'AbortError') {
            console.error('Operational table refresh failed.', error)
        }
    } finally {
        if (operationalRefreshInFlight.get(targetSelector) === controller) {
            operationalRefreshInFlight.delete(targetSelector)
        }
    }
}

document.addEventListener('htmx:beforeRequest', (event) => {
    const requestElement = event.detail?.elt
    const progressOwner = requestElement?.closest?.('[data-operational-progress-title]')
    const request = event.detail?.xhr

    if (!progressOwner || !request) {
        return
    }

    const existingActivityId = operationalActivityByRequest.get(request)
    if (existingActivityId) {
        window.finishOperationalActivity(existingActivityId)
    }

    const activityId = window.startOperationalActivity(
        progressOwner.dataset.operationalProgressTitle,
        progressOwner.dataset.operationalProgressMessage
    )
    operationalActivityByRequest.set(request, activityId)
    request.__kaoriOperationalActivityId = activityId
    progressOwner.dataset.operationalActivityId = activityId
})

const finishOperationalProgressRequest = (event) => {
    const request = event.detail?.xhr
    const requestElement = event.detail?.elt
    const progressOwner = requestElement?.closest?.('[data-operational-progress-title]')
    const activityId = request
        ? operationalActivityByRequest.get(request) || request.__kaoriOperationalActivityId
        : progressOwner?.dataset.operationalActivityId

    window.finishOperationalActivity(activityId)

    if (request) {
        operationalActivityByRequest.delete(request)
        delete request.__kaoriOperationalActivityId
    }

    if (progressOwner) {
        delete progressOwner.dataset.operationalActivityId
    }
}

document.addEventListener('htmx:beforeOnLoad', finishOperationalProgressRequest)
document.addEventListener('htmx:beforeSwap', finishOperationalProgressRequest)
document.addEventListener('htmx:afterRequest', (event) => {
    finishOperationalProgressRequest(event)

    const requestElement = event.detail?.elt
    const progressOwner = requestElement?.closest?.('[data-operational-refresh-url]')
    const refreshUrl = progressOwner?.dataset.operationalRefreshUrl

    if (refreshUrl) {
        window.refreshOperationalTable(refreshUrl)
    }
})
document.addEventListener('htmx:responseError', finishOperationalProgressRequest)
document.addEventListener('htmx:sendError', finishOperationalProgressRequest)
document.addEventListener('htmx:timeout', finishOperationalProgressRequest)
document.addEventListener('htmx:abort', finishOperationalProgressRequest)

document.addEventListener('submit', (event) => {
    const submitButton = event.submitter

    if (!submitButton || !submitButton.matches('[data-operation-submit]')) {
        return
    }

    submitButton.disabled = true
    submitButton.classList.add('cursor-wait', 'opacity-75')

    const icon = submitButton.querySelector('[data-lucide]')
    const label = submitButton.querySelector('[data-operation-submit-label]')
    const loadingLabel = submitButton.dataset.loadingLabel

    if (icon) {
        icon.classList.add('animate-spin')
    }

    if (label && loadingLabel) {
        label.textContent = loadingLabel
    }
})

document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('theme-toggle')

    if (!button) {
        return
    }

    button.addEventListener('click', () => {
        document.documentElement.classList.toggle('dark')

        const dark = document.documentElement.classList.contains('dark')

        localStorage.setItem('theme', dark ? 'dark' : 'light')
    })
})
