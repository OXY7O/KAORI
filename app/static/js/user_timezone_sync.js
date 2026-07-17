;(() => {
    const syncNode = document.getElementById('kaori-user-timezone-sync')
    if (!syncNode || syncNode.dataset.mode !== 'automatic') return

    const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone
    const storedTimezone = syncNode.dataset.timezone
    const syncUrl = syncNode.dataset.url
    const csrfToken = syncNode.dataset.csrf

    if (!browserTimezone || !syncUrl || browserTimezone === storedTimezone) return

    const attemptKey = `kaori.timezone-sync:${browserTimezone}`
    if (sessionStorage.getItem(attemptKey) === 'pending') return
    sessionStorage.setItem(attemptKey, 'pending')

    fetch(syncUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ timezone: browserTimezone }),
    })
        .then((response) => {
            if (!response.ok) throw new Error(`Timezone synchronization failed with status ${response.status}`)
            return response.json()
        })
        .then((payload) => {
            sessionStorage.removeItem(attemptKey)
            if (payload.status === 'updated') window.location.reload()
        })
        .catch((error) => {
            sessionStorage.removeItem(attemptKey)
            console.warn('KAORI browser timezone synchronization failed.', error)
        })
})()
