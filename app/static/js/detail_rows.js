(() => {
    const SELECTOR = '[data-detail-toggle]'
    const inFlight = new Map()

    function refreshIcons() {
        if (window.lucide) window.lucide.createIcons()
    }

    function processHtmx(root) {
        if (window.htmx?.process) window.htmx.process(root)
    }

    function setButtonState(button, open) {
        const label = button.querySelector('[data-detail-toggle-label]')
        const leadingIcon = button.querySelector('[data-detail-leading-icon] [data-lucide]')
        const chevron = button.querySelector('[data-detail-chevron]')

        button.setAttribute('aria-expanded', open ? 'true' : 'false')
        button.dataset.detailState = open ? 'open' : 'closed'
        button.classList.toggle('border-brand-outline', open)
        button.classList.toggle('bg-kaori-soft', open)
        button.classList.toggle('text-kaori-primary-dark', open)
        if (label) label.textContent = open
            ? (button.dataset.detailCloseLabel || 'Close Details')
            : (button.dataset.detailOpenLabel || 'View Details')
        if (leadingIcon) leadingIcon.setAttribute('data-lucide', open ? 'x' : 'eye')
        if (chevron) chevron.classList.toggle('rotate-180', open)
    }

    function resolveElements(button) {
        const targetId = button.dataset.detailTarget || ''
        const rowId = button.dataset.detailRow || ''
        return {
            target: targetId ? document.getElementById(targetId) : null,
            row: rowId ? document.getElementById(rowId) : null,
        }
    }

    function cancelRequest(target) {
        const controller = inFlight.get(target.id)
        if (controller) controller.abort()
        inFlight.delete(target.id)
    }

    function closeButton(button) {
        const { target, row } = resolveElements(button)

        if (target) {
            cancelRequest(target)
            if (target.dataset.detailStatic !== 'true') target.innerHTML = ''
            target.dataset.open = 'false'
            target.removeAttribute('aria-busy')
        }
        if (row) row.classList.add('hidden')
        setButtonState(button, false)
    }

    function closeGroup(group, exceptButton = null) {
        document.querySelectorAll(SELECTOR).forEach((button) => {
            if (button !== exceptButton && (button.dataset.detailGroup || 'default') === group) {
                closeButton(button)
            }
        })
    }

    function renderLoading(target, button) {
        const context = button?.dataset.detailContext || 'Inventory Details'
        target.setAttribute('aria-busy', 'true')
        target.innerHTML = `
            <div class="bg-kaori-mist/50 px-3 py-3 sm:px-4 sm:py-4">
                <div class="flex min-h-28 items-center justify-center gap-3 rounded-2xl border border-brand-outline bg-surface-card px-5 py-6 shadow-sm">
                    <span class="h-5 w-5 animate-spin rounded-full border-2 border-outline-default border-t-kaori-primary" aria-hidden="true"></span>
                    <div>
                        <p class="text-sm font-semibold leading-5 text-content-primary">Loading ${context}</p>
                        <p class="mt-1 text-xs leading-5 text-content-muted">Reading the latest committed KAORI evidence.</p>
                    </div>
                </div>
            </div>
        `
    }

    function renderError(target, button) {
        const context = button?.dataset.detailContext || 'Inventory Details'
        target.removeAttribute('aria-busy')
        target.innerHTML = `
            <div class="bg-kaori-mist/50 px-3 py-3 sm:px-4 sm:py-4">
                <div class="rounded-2xl border border-status-critical-border bg-status-critical-soft px-5 py-5">
                    <p class="text-sm font-semibold leading-5 text-status-critical-text">Unable to Load ${context}</p>
                    <p class="mt-1 text-xs leading-5 text-status-critical-text">Refresh the current workspace or close and open this detail again.</p>
                </div>
            </div>
        `
    }

    async function loadDetail(button, target, detailUrl) {
        cancelRequest(target)
        const controller = new AbortController()
        inFlight.set(target.id, controller)

        try {
            const response = await fetch(detailUrl, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'HX-Request': 'true',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                signal: controller.signal,
            })

            if (!response.ok) throw new Error(`Detail request failed with ${response.status}`)
            const html = await response.text()

            if (target.dataset.open !== 'true') return
            target.innerHTML = html
            target.removeAttribute('aria-busy')
            processHtmx(target)
            refreshIcons()
        } catch (error) {
            if (error.name === 'AbortError') return
            renderError(target, button)
            setButtonState(button, true)
            target.dataset.open = 'true'
        } finally {
            if (inFlight.get(target.id) === controller) inFlight.delete(target.id)
        }
    }

    function openButton(button) {
        const { target, row } = resolveElements(button)
        const detailUrl = button.dataset.detailUrl || ''
        if (!target || !row) return

        closeGroup(button.dataset.detailGroup || 'default', button)
        row.classList.remove('hidden')
        target.dataset.open = 'true'
        setButtonState(button, true)

        if (target.dataset.detailStatic === 'true') {
            target.removeAttribute('aria-busy')
            refreshIcons()
            return
        }

        if (!detailUrl) {
            closeButton(button)
            return
        }

        renderLoading(target, button)
        refreshIcons()
        loadDetail(button, target, detailUrl)
    }

    document.addEventListener('click', (event) => {
        const element = event.target instanceof Element ? event.target : null
        const button = element?.closest(SELECTOR)
        if (!button) return

        event.preventDefault()
        const { target, row } = resolveElements(button)
        if (!target || !row) return

        if (target.dataset.open === 'true') {
            closeButton(button)
            refreshIcons()
            return
        }

        openButton(button)
    })
})()

;(() => {
    const HOST_SELECTOR = '[data-resource-detail-modal-host]'
    const TOGGLE_SELECTOR = '[data-resource-detail-toggle]'
    const DETAIL_PARAM = 'detail'
    const SESSION_TOKEN = `${Date.now()}-${Math.random().toString(36).slice(2)}`
    let activeController = null
    let activeOpener = null
    let activeDetailId = null
    let lockedMain = null
    let previousMainOverflowY = ''
    let lockedMainScrollTop = 0
    let closeTimer = null

    function host() {
        return document.querySelector(HOST_SELECTOR)
    }

    function refreshIcons() {
        if (window.renderKaoriIcons) {
            window.renderKaoriIcons()
        } else if (window.lucide) {
            window.lucide.createIcons()
        }
    }

    function processHtmx(root) {
        if (window.htmx?.process) window.htmx.process(root)
    }

    function modalElements(modalHost) {
        return {
            dialog: modalHost.querySelector('[data-resource-detail-dialog]'),
            header: modalHost.querySelector('[data-resource-detail-header-host]'),
            summary: modalHost.querySelector('[data-resource-detail-summary-host]'),
            loadingBar: modalHost.querySelector('[data-resource-detail-loading-bar]'),
            loading: modalHost.querySelector('[data-resource-detail-loading]'),
            error: modalHost.querySelector('[data-resource-detail-error]'),
            content: modalHost.querySelector('[data-resource-detail-content]'),
        }
    }

    function lockBackground() {
        if (lockedMain) return
        lockedMain = document.querySelector('main')
        if (!lockedMain) return
        previousMainOverflowY = lockedMain.style.overflowY
        lockedMainScrollTop = lockedMain.scrollTop
        lockedMain.style.overflowY = 'hidden'
        lockedMain.scrollTop = lockedMainScrollTop
    }

    function unlockBackground() {
        if (!lockedMain) return
        lockedMain.style.overflowY = previousMainOverflowY
        lockedMain.scrollTop = lockedMainScrollTop
        lockedMain = null
        previousMainOverflowY = ''
        lockedMainScrollTop = 0
    }

    function isDrawer(modalHost) {
        return modalHost.dataset.resourceDetailPresentation === 'drawer'
    }

    function hideHost(modalHost) {
        modalHost.classList.add('hidden')
        modalHost.classList.remove('flex', 'pointer-events-none')
        modalHost.setAttribute('aria-hidden', 'true')
        unlockBackground()
    }

    function setModalVisible(modalHost, visible, afterHidden = null) {
        const elements = modalElements(modalHost)
        const drawer = isDrawer(modalHost)

        if (closeTimer) {
            window.clearTimeout(closeTimer)
            closeTimer = null
        }

        if (visible) {
            modalHost.classList.remove('hidden', 'pointer-events-none')
            modalHost.classList.add('flex')
            modalHost.setAttribute('aria-hidden', 'false')

            if (drawer) {
                unlockBackground()
                elements.dialog?.classList.add('translate-x-full')
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => elements.dialog?.classList.remove('translate-x-full'))
                })
            } else {
                lockBackground()
            }
            return
        }

        if (drawer && elements.dialog) {
            modalHost.classList.add('pointer-events-none')
            elements.dialog.classList.add('translate-x-full')
            closeTimer = window.setTimeout(() => {
                hideHost(modalHost)
                closeTimer = null
                if (afterHidden) afterHidden()
            }, 200)
            return
        }

        hideHost(modalHost)
        if (afterHidden) afterHidden()
    }

    function setLoading(elements) {
        elements.loadingBar?.classList.remove('hidden')
        elements.loading?.classList.remove('hidden')
        elements.error?.classList.add('hidden')
        elements.content?.classList.add('hidden')
        elements.summary?.classList.add('hidden')
        if (elements.summary) elements.summary.innerHTML = ''
        if (elements.content) elements.content.innerHTML = ''
    }

    function setError(elements) {
        elements.loadingBar?.classList.add('hidden')
        elements.loading?.classList.add('hidden')
        elements.error?.classList.remove('hidden')
        elements.content?.classList.add('hidden')
        elements.summary?.classList.add('hidden')
        refreshIcons()
    }

    function setGenericHeader(elements, type, name, contextLabel = 'Inventory', presentation = 'modal') {
        if (!elements.header) return
        const icon = presentation === 'drawer' ? 'panel-right-open' : 'panel-top-open'
        elements.header.innerHTML = `
            <div class="flex min-w-0 items-start gap-3">
                <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-kaori-soft text-kaori-primary" aria-hidden="true">
                    <i data-lucide="${icon}" class="h-5 w-5"></i>
                </span>
                <div class="min-w-0">
                    <p class="text-xs font-semibold leading-5 text-kaori-primary">${escapeHtml(contextLabel)} Details</p>
                    <h2 id="resource-detail-modal-title" class="break-words text-lg font-semibold leading-6 text-content-primary [overflow-wrap:anywhere]">${escapeHtml(name || ((type || 'Resource') + ' Details'))}</h2>
                    <p class="mt-1 text-sm leading-5 text-content-muted">Loading ${escapeHtml(String(contextLabel || 'Resource').toLowerCase())} evidence.</p>
                </div>
            </div>
        `
    }

    function escapeHtml(value) {
        return String(value || '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;')
    }

    function normalizeDetailMarkup(html, elements) {
        const staging = document.createElement('div')
        staging.innerHTML = html

        const workspace = staging.querySelector('[data-kaori-detail-variant]')
        const shell = workspace?.firstElementChild || workspace || staging
        const header = shell.querySelector(':scope > [data-resource-detail-header]')
        const summary = shell.querySelector(':scope > [data-resource-detail-summary]')

        if (header && elements.header) {
            elements.header.innerHTML = header.innerHTML
            const title = elements.header.querySelector('h1, h2, h3, h4')
            if (title) title.id = 'resource-detail-modal-title'
            header.remove()
        }

        if (summary && elements.summary) {
            elements.summary.innerHTML = summary.outerHTML
            elements.summary.classList.remove('hidden')
            summary.remove()
        } else if (elements.summary) {
            elements.summary.classList.add('hidden')
            elements.summary.innerHTML = ''
        }

        if (elements.content) {
            elements.content.innerHTML = shell.innerHTML
            elements.content.classList.remove('hidden')
        }
        elements.loadingBar?.classList.add('hidden')
        elements.loading?.classList.add('hidden')
        elements.error?.classList.add('hidden')
        processHtmx(elements.content)
        refreshIcons()
    }

    function updateUrl(detailId, mode = 'push') {
        const url = new URL(window.location.href)
        if (detailId) url.searchParams.set(DETAIL_PARAM, detailId)
        else url.searchParams.delete(DETAIL_PARAM)

        const state = detailId
            ? { ...(history.state || {}), kaoriResourceDetail: true, detailId: String(detailId), detailSession: SESSION_TOKEN }
            : { ...(history.state || {}), kaoriResourceDetail: false, detailId: null, detailSession: null }

        if (mode === 'replace') history.replaceState(state, '', url)
        else history.pushState(state, '', url)
    }

    function detailUrlFromTemplate(modalHost, detailId) {
        const template = modalHost.dataset.detailUrlTemplate || ''
        if (!template) return ''
        if (template.includes('__detail__')) {
            return template.replace('__detail__', encodeURIComponent(detailId))
        }
        return template.replace(/\/0\/details(?:\?.*)?$/, `/${encodeURIComponent(detailId)}/details`)
    }

    async function loadModalDetail(modalHost, detailId, detailUrl, type, name) {
        const elements = modalElements(modalHost)
        if (activeController) activeController.abort()
        activeController = new AbortController()
        activeDetailId = String(detailId)

        setModalVisible(modalHost, true)
        setGenericHeader(
            elements,
            type || modalHost.dataset.resourceType,
            name,
            modalHost.dataset.detailContextLabel || 'Inventory',
            modalHost.dataset.resourceDetailPresentation || 'modal'
        )
        setLoading(elements)
        refreshIcons()
        requestAnimationFrame(() => elements.dialog?.focus())

        try {
            const response = await fetch(detailUrl, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'HX-Request': 'true',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                signal: activeController.signal,
            })
            if (!response.ok) throw new Error(`Detail request failed with ${response.status}`)
            const html = await response.text()
            if (activeDetailId !== String(detailId)) return
            normalizeDetailMarkup(html, elements)
        } catch (error) {
            if (error.name === 'AbortError') return
            setError(elements)
        } finally {
            activeController = null
        }
    }

    function openFromButton(button, historyMode = 'replace') {
        const modalHost = host()
        if (!modalHost) return
        const detailId = button.dataset.detailId || ''
        const detailUrl = button.dataset.detailUrl || ''
        if (!detailId || !detailUrl) return

        activeOpener = button
        if (historyMode) updateUrl(detailId, historyMode)
        loadModalDetail(
            modalHost,
            detailId,
            detailUrl,
            button.dataset.detailType || modalHost.dataset.resourceType,
            button.dataset.detailName || ''
        )
    }

    function openFromUrl(detailId) {
        const modalHost = host()
        if (!modalHost || !detailId) return
        const button = [...document.querySelectorAll(TOGGLE_SELECTOR)]
            .find((candidate) => candidate.dataset.detailId === String(detailId))
        if (button) {
            activeOpener = button
            openFromButton(button, null)
            return
        }
        const detailUrl = detailUrlFromTemplate(modalHost, detailId)
        if (!detailUrl) return
        activeOpener = null
        loadModalDetail(modalHost, detailId, detailUrl, modalHost.dataset.resourceType, `${modalHost.dataset.resourceType || 'Resource'} #${detailId}`)
    }

    function closeModal({ updateHistory = true } = {}) {
        const modalHost = host()
        if (!modalHost || modalHost.classList.contains('hidden')) return
        if (activeController) activeController.abort()
        activeController = null
        activeDetailId = null

        if (updateHistory) updateUrl(null, 'replace')

        const opener = activeOpener
        activeOpener = null
        setModalVisible(modalHost, false, () => {
            const elements = modalElements(modalHost)
            if (elements.content) elements.content.innerHTML = ''
            if (elements.summary) {
                elements.summary.innerHTML = ''
                elements.summary.classList.add('hidden')
            }
            elements.error?.classList.add('hidden')
            elements.loading?.classList.remove('hidden')
            if (opener?.isConnected) opener.focus()
        })
    }

    function focusableElements(dialog) {
        return [...dialog.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
            .filter((element) => !element.closest('[hidden]') && element.offsetParent !== null)
    }

    document.addEventListener('click', (event) => {
        const element = event.target instanceof Element ? event.target : null
        const toggle = element?.closest(TOGGLE_SELECTOR)
        if (toggle) {
            event.preventDefault()
            openFromButton(toggle, 'replace')
            return
        }

        if (element?.closest('[data-resource-detail-close], [data-resource-detail-backdrop]')) {
            event.preventDefault()
            closeModal()
        }
    })

    document.addEventListener('keydown', (event) => {
        const modalHost = host()
        if (!modalHost || modalHost.classList.contains('hidden')) return
        const dialog = modalHost.querySelector('[data-resource-detail-dialog]')

        if (event.key === 'Escape') {
            event.preventDefault()
            event.stopPropagation()
            closeModal()
            return
        }

        if (event.key !== 'Tab' || !dialog) return
        const focusables = focusableElements(dialog)
        if (!focusables.length) {
            event.preventDefault()
            dialog.focus()
            return
        }
        const first = focusables[0]
        const last = focusables[focusables.length - 1]
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault()
            last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault()
            first.focus()
        }
    })

    window.addEventListener('popstate', () => {
        const modalHost = host()
        if (!modalHost) return
        const detailId = new URL(window.location.href).searchParams.get(DETAIL_PARAM)
        if (detailId) openFromUrl(detailId)
        else closeModal({ updateHistory: false })
    })

    document.addEventListener('DOMContentLoaded', () => {
        const modalHost = host()
        if (!modalHost) return
        const detailId = new URL(window.location.href).searchParams.get(DETAIL_PARAM)
        if (detailId) openFromUrl(detailId)
    })
})()
