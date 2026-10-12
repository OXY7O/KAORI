// Artifact Registry Dependency Topology (#1692).
// Presentation only: the source of truth is the committed, bounded Python graph.
const $ = (id) => document.getElementById(id)
const canvas = $('registry-topology-canvas')
const form = $('registry-topology-filters')

if (canvas && form) {
    const graphTab = $('registry-topology-graph-tab')
    const listTab = $('registry-topology-list-tab')
    const graphShell = $('registry-topology-canvas-shell')
    const listShell = $('registry-topology-list-shell')
    const tbody = $('registry-topology-resource-rows')
    const status = $('registry-topology-status')
    const warning = $('registry-topology-warning')
    const errorPanel = $('registry-topology-error')
    const empty = $('registry-topology-empty')
    const inspector = $('registry-topology-inspector')
    const inspectorContent = $('registry-topology-inspector-content')
    const backdrop = $('registry-topology-backdrop')
    const close = $('registry-topology-inspector-close')
    const previous = $('registry-topology-prev')
    const next = $('registry-topology-next')
    let cy = null
    let renderer = null
    let payload = { nodes: [], edges: [], bindings: [], summary: {}, evidence: {} }
    let view = new URL(window.location.href).searchParams.get('view') === 'list' ? 'list' : 'graph'
    let listPage = 1
    let controller = null
    const pageSize = 5

    const token = (name, fallback) =>
        window.getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    const elements = (tag, className, text) => {
        const el = document.createElement(tag)
        if (className) el.className = className
        if (text !== undefined) el.textContent = String(text ?? '')
        return el
    }
    const safeLabel = (value) => String(value ?? 'Not Collected')
    const appendField = (parent, name, value) => {
        const row = elements('div', 'flex flex-wrap items-start justify-between gap-3 border-b border-outline-subtle py-2')
        row.append(elements('span', 'text-xs text-content-muted', name))
        row.append(elements('span', 'max-w-full break-all text-right text-xs font-medium text-content-primary', safeLabel(value)))
        parent.append(row)
    }
    const link = (label, href) => {
        const el = elements('a', 'inline-flex items-center rounded-lg border border-outline-default px-3 py-2 text-xs font-semibold text-kaori-primary hover:bg-surface-elevated', label)
        el.href = href
        return el
    }
    let inspectorReturnFocus = null
    const closeInspector = () => {
        const wasOpen = !inspector.classList.contains('hidden')
        inspector.classList.add('hidden')
        backdrop.classList.add('hidden')
        if (wasOpen && inspectorReturnFocus?.isConnected) inspectorReturnFocus.focus()
    }
    const openInspector = () => {
        if (inspector.classList.contains('hidden')) inspectorReturnFocus = document.activeElement
        inspector.classList.remove('hidden')
        backdrop.classList.remove('hidden')
        close.focus()
    }
    close.addEventListener('click', closeInspector)
    backdrop.addEventListener('click', closeInspector)
    document.addEventListener('keydown', (event) => {
        if (inspector.classList.contains('hidden')) return
        if (event.key === 'Escape') {
            event.preventDefault()
            closeInspector()
        }
        if (event.key !== 'Tab') return
        const focusables = [...inspector.querySelectorAll('button:not([disabled]), a[href]')]
        if (!focusables.length) return
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

    const associatedBindings = (nodeId) => {
        if (!cy) return payload.bindings.filter((item) => item.node_id === nodeId)
        const selected = cy.$id(nodeId)
        if (!selected.length) return []
        const related = new Set([nodeId])
        selected.successors('node').forEach((node) => related.add(node.id()))
        return payload.bindings.filter((item) => related.has(item.node_id))
    }

    const inspect = (node) => {
        const data = node.data()
        inspectorContent.replaceChildren()
        inspectorContent.append(elements('p', 'text-xs font-semibold uppercase tracking-wide text-kaori-primary', safeLabel(data.type)))
        inspectorContent.append(elements('h4', 'break-words text-lg font-semibold text-content-primary', safeLabel(data.label)))
        if (data.subtitle) inspectorContent.append(elements('p', 'text-sm text-content-muted', data.subtitle))
        const info = elements('div', 'rounded-xl border border-outline-default bg-surface-card px-4 py-2')
        if (data.type === 'artifact') {
            appendField(info, 'Registry Source', data.source)
            appendField(info, 'Artifact Digest', data.digest)
            appendField(info, 'Scan', data.scan_status)
            appendField(info, 'Critical / High', `${data.critical} / ${data.high}`)
        } else if (data.type === 'cluster') {
            appendField(info, 'Kubernetes Cluster ID', data.cluster_id)
        } else {
            appendField(info, 'Resource Type', data.type)
        }
        inspectorContent.append(info)

        const bindings = associatedBindings(data.id)
        inspectorContent.append(elements('h5', 'text-sm font-semibold text-content-primary', `Visible Runtime Evidence (${bindings.length})`))
        if (bindings.length) {
            for (const item of bindings.slice(0, 12)) {
                const box = elements('div', 'space-y-1 rounded-lg border border-outline-subtle bg-surface-elevated p-3')
                box.append(elements('p', 'text-xs font-semibold text-content-primary', `${item.cluster} / ${item.namespace}`))
                box.append(elements('p', 'text-xs text-content-secondary', `${item.workload} · ${item.pod}`))
                box.append(elements('p', 'text-xs text-content-muted', `${item.match} · ${item.security} · ${item.containers.length} container(s)`))
                inspectorContent.append(box)
            }
            if (bindings.length > 12) {
                inspectorContent.append(elements('p', 'text-xs text-content-muted', `${bindings.length - 12} more displayed bindings; see Resource List.`))
            }
        } else {
            inspectorContent.append(elements('p', 'text-sm text-content-muted', 'No runtime bindings in the displayed slice.'))
        }
        inspectorContent.append(elements('p', 'text-xs text-content-muted', 'Evidence is limited to the selected committed graph slice; inspect snapshot readiness and omitted counts.'))
        if (data.type === 'artifact' && data.url) inspectorContent.append(link('Open Runtime Bindings', data.url))
        openInspector()
    }

    const inspectBinding = (item) => {
        const match = `${item.match} · ${item.confidence} confidence`
        inspectorContent.replaceChildren()
        inspectorContent.append(elements('h4', 'break-words text-lg font-semibold text-content-primary', item.artifact))
        const info = elements('div', 'rounded-xl border border-outline-default bg-surface-card px-4 py-2')
        appendField(info, 'Registry Source', item.source)
        appendField(info, 'Artifact Digest', item.digest)
        appendField(info, 'Cluster', item.cluster)
        appendField(info, 'Namespace', item.namespace)
        appendField(info, 'Workload', item.workload)
        appendField(info, 'Pod', item.pod)
        appendField(info, 'Containers', item.containers.map((c) => `${c.name} (${c.kind})`).join(', '))
        appendField(info, 'Image Reference', item.image_reference)
        appendField(info, 'Match', match)
        appendField(info, 'Artifact Security', item.security)
        appendField(info, 'Correlated At', item.observed_at)
        appendField(info, 'Registry Observed At', item.registry_observed_at)
        appendField(info, 'Kubernetes Observed At', item.pod_collected_at)
        inspectorContent.append(info)
        inspectorContent.append(elements('p', 'text-xs text-content-muted', 'Digest matching is immutable identity evidence. Tag-only matches are provisional, not verified image equivalence.'))
        inspectorContent.append(link('Open Runtime Bindings', item.url))
        openInspector()
    }

    const renderList = () => {
        tbody.replaceChildren()
        const total = payload.bindings.length
        const maxPage = Math.max(Math.ceil(total / pageSize), 1)
        listPage = Math.min(Math.max(listPage, 1), maxPage)
        const page = payload.bindings.slice((listPage - 1) * pageSize, listPage * pageSize)
        for (const item of page) {
            const tr = elements('tr', 'border-b border-outline-subtle')
            const a = elements('td', 'px-4 py-3 text-sm font-medium text-content-primary')
            a.append(elements('div', '', item.artifact))
            a.append(elements('div', 'text-xs text-content-muted', item.digest.slice(0, 28)))
            const b = elements('td', 'px-4 py-3 text-xs text-content-secondary')
            b.append(elements('p', 'font-semibold text-content-primary', `${item.cluster} · ${item.namespace}`))
            b.append(elements('p', '', `${item.workload} · ${item.pod}`))
            const c = elements('td', 'px-4 py-3 text-xs text-content-primary', item.match)
            const d = elements('td', 'px-4 py-3 text-xs text-content-primary', item.security)
            const e = elements('td', 'px-4 py-3 text-right')
            const button = elements('button', 'rounded-lg border border-outline-default px-3 py-2 text-xs font-semibold text-kaori-primary', 'Inspect')
            button.type = 'button'
            button.addEventListener('click', () => inspectBinding(item))
            e.append(button)
            tr.append(a, b, c, d, e)
            tbody.append(tr)
        }
        if (!page.length) {
            const tr = elements('tr')
            const td = elements('td', 'px-4 py-8 text-center text-sm text-content-muted', 'No visible bindings. Check filters and evidence readiness.')
            td.colSpan = 5
            tr.append(td)
            tbody.append(tr)
        }
        $('registry-topology-list-count').textContent =
            `Showing ${page.length ? (listPage - 1) * pageSize + 1 : 0}–${(listPage - 1) * pageSize + page.length} of ${total} visible bindings (${payload.summary.total_bindings ?? 0} in scope).`
        previous.disabled = listPage <= 1
        next.disabled = listPage >= maxPage
    }

    const setView = (value) => {
        view = value
        const isGraph = value === 'graph'
        graphShell.classList.toggle('hidden', !isGraph)
        listShell.classList.toggle('hidden', isGraph)
        graphTab.setAttribute('aria-pressed', String(isGraph))
        listTab.setAttribute('aria-pressed', String(!isGraph))
        $('registry-topology-fit').disabled = !isGraph || !cy
        $('registry-topology-reset').disabled = !isGraph || !cy
        $('registry-topology-export').disabled = !isGraph || !cy
        const url = new URL(window.location.href)
        if (isGraph) url.searchParams.delete('view')
        else url.searchParams.set('view', 'list')
        window.history.replaceState({}, '', url)
        if (isGraph && cy) cy.resize()
    }
    graphTab.addEventListener('click', () => setView('graph'))
    listTab.addEventListener('click', () => setView('list'))
    previous.addEventListener('click', () => { listPage -= 1; renderList() })
    next.addEventListener('click', () => { listPage += 1; renderList() })

    const renderGraph = async () => {
        if (!renderer) {
            const module = await import(canvas.dataset.rendererUrl)
            renderer = module.c || module.default
            if (typeof renderer !== 'function') throw new Error('Cytoscape module is unavailable')
        }
        if (cy) cy.destroy()
        const colors = {
            artifact: token('--kaori-topology-domain-configuration-border', 'CanvasText'),
            cluster: token('--kaori-topology-domain-scope-border', 'CanvasText'),
            namespace: token('--kaori-topology-domain-scope-border', 'CanvasText'),
            workload: token('--kaori-topology-domain-compute-border', 'CanvasText'),
            pod: token('--kaori-topology-domain-compute-border', 'CanvasText'),
        }
        const fills = {
            artifact: token('--kaori-topology-domain-configuration-fill', 'Canvas'),
            cluster: token('--kaori-topology-domain-scope-fill', 'Canvas'),
            namespace: token('--kaori-topology-domain-scope-fill', 'Canvas'),
            workload: token('--kaori-topology-domain-compute-fill', 'Canvas'),
            pod: token('--kaori-topology-domain-compute-fill', 'Canvas'),
        }
        const textColors = {
            artifact: token('--kaori-topology-domain-configuration-text', 'CanvasText'),
            cluster: token('--kaori-topology-domain-scope-text', 'CanvasText'),
            namespace: token('--kaori-topology-domain-scope-text', 'CanvasText'),
            workload: token('--kaori-topology-domain-compute-text', 'CanvasText'),
            pod: token('--kaori-topology-domain-compute-text', 'CanvasText'),
        }
        cy = renderer({
            container: canvas,
            elements: [...payload.nodes, ...payload.edges],
            layout: {
                name: 'breadthfirst',
                directed: true,
                roots: payload.nodes.filter((n) => n.data.type === 'artifact').map((n) => n.data.id),
                padding: 42,
                spacingFactor: 1.35,
            },
            minZoom: 0.2,
            maxZoom: 2.2,
            wheelSensitivity: 0.18,
            style: [
                {
                    selector: 'node',
                    style: {
                        label: (ele) => `${ele.data('label')}\n${ele.data('subtitle') || ele.data('type')}`,
                        shape: 'round-rectangle',
                        width: 170,
                        height: 56,
                        'background-color': (ele) => fills[ele.data('type')] || 'Canvas',
                        'border-color': (ele) => colors[ele.data('type')] || 'CanvasText',
                        'border-width': 1.5,
                        color: (ele) => textColors[ele.data('type')] || 'CanvasText',
                        'font-size': 10,
                        'font-weight': 600,
                        'text-wrap': 'ellipsis',
                        'text-max-width': 155,
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'overlay-opacity': 0,
                    },
                },
                {
                    selector: 'edge',
                    style: {
                        width: 1.8,
                        'curve-style': 'taxi',
                        'taxi-direction': 'downward',
                        'line-color': (ele) =>
                            ele.data('relationship') === 'runtime_usage' &&
                            ['medium', 'mixed'].includes(ele.data('confidence'))
                                ? token('--kaori-status-warning', 'CanvasText')
                                : token('--kaori-topology-edge-contains', 'CanvasText'),
                        'target-arrow-shape': 'none',
                        'line-style': (ele) =>
                            ele.data('relationship') === 'contains' ? 'dashed' : 'solid',
                        'overlay-opacity': 0,
                    },
                },
                {
                    selector: ':selected',
                    style: {
                        'border-width': 3,
                        'border-color': token('--kaori-topology-domain-configuration-border', 'CanvasText'),
                    },
                },
            ],
        })
        cy.on('tap', 'node', (event) => inspect(event.target))
        cy.on('tap', 'edge', (event) => {
            const edge = event.target
            inspectorContent.replaceChildren()
            inspectorContent.append(elements('h4', 'text-lg font-semibold text-content-primary', 'Relationship Evidence'))
            const details = elements('div', 'rounded-lg border border-outline-default p-4')
            appendField(details, 'Relationship', edge.data('relationship'))
            appendField(details, 'Match Confidence', edge.data('confidence'))
            appendField(details, 'From', edge.source().data('label'))
            appendField(details, 'To', edge.target().data('label'))
            inspectorContent.append(details)
            inspectorContent.append(elements('p', 'text-xs text-content-muted', 'Context edges are structural. A mixed runtime edge includes both digest and tag evidence. Inspect exact binding rows for certainty.'))
            openInspector()
        })
        cy.fit(undefined, 36)
        setView(view)
    }

    const reload = async () => {
        if (controller) controller.abort()
        controller = new AbortController()
        status.textContent = 'Loading committed dependency evidence…'
        warning.classList.add('hidden')
        errorPanel.classList.add('hidden')
        closeInspector()
        const params = new URLSearchParams(new FormData(form))
        const dataUrl = new URL(canvas.dataset.url, window.location.origin)
        dataUrl.search = params.toString()
        try {
            const response = await fetch(dataUrl, {
                headers: { Accept: 'application/json' },
                signal: controller.signal,
                credentials: 'same-origin',
            })
            if (!response.ok) throw new Error(`Graph request failed (HTTP ${response.status})`)
            payload = await response.json()
            listPage = 1
            renderList()
            const summary = payload.summary
            const evidence = payload.evidence
            status.textContent = `${summary.artifacts_visible} artifacts · ${summary.workloads_visible} workloads · ${summary.pods_visible} pods · ${summary.displayed_bindings}/${summary.total_bindings} bindings. Evidence: ${evidence.title}.`
            if (evidence.status !== 'ready' || summary.truncated) {
                warning.classList.remove('hidden')
                const qualification = evidence.status === 'ready' ? '' : `${evidence.description} `
                const bounded = summary.truncated ? `Graph is bounded to ${summary.max_visible_bindings} bindings; ${summary.omitted_bindings} are omitted from this view. Refine filters for the complete impact scope.` : ''
                warning.textContent = qualification + bounded
            }
            empty.classList.toggle('hidden', payload.nodes.length > 0)
            empty.classList.toggle('flex', payload.nodes.length === 0)
            try {
                await renderGraph()
            } catch (renderError) {
                console.error('Dependency topology rendering unavailable:', renderError)
                errorPanel.textContent = 'Graph renderer unavailable. Resource List remains accessible.'
                errorPanel.classList.remove('hidden')
                setView('list')
            }
        } catch (requestError) {
            if (requestError.name === 'AbortError') return
            console.error('Dependency topology data load failed:', requestError)
            errorPanel.textContent = 'Unable to load committed dependency evidence. Try Reload Snapshot or return to Runtime Bindings.'
            errorPanel.classList.remove('hidden')
            status.textContent = 'Topology unavailable — no evidence conclusion can be drawn.'
        }
    }

    form.addEventListener('submit', (event) => {
        event.preventDefault()
        const params = new URLSearchParams(new FormData(form))
        const url = new URL(window.location.href)
        url.search = params.toString()
        if (view === 'list') url.searchParams.set('view', 'list')
        window.history.replaceState({}, '', url)
        reload()
    })
    form.querySelectorAll('select').forEach((select) => {
        select.addEventListener('change', () => form.requestSubmit())
    })
    $('registry-topology-reload').addEventListener('click', reload)
    $('registry-topology-fit').addEventListener('click', () => cy?.fit(undefined, 36))
    $('registry-topology-reset').addEventListener('click', () => cy?.layout({
        name: 'breadthfirst',
        directed: true,
        roots: payload.nodes.filter((n) => n.data.type === 'artifact').map((n) => n.data.id),
        padding: 42,
        spacingFactor: 1.35,
    }).run())
    $('registry-topology-export').addEventListener('click', () => {
        if (!cy) return
        const output = cy.png({ full: true, scale: 2, bg: window.getComputedStyle(document.body).backgroundColor })
        const a = document.createElement('a')
        a.href = output
        a.download = 'kaori-artifact-dependency-topology.png'
        a.click()
    })
    setView(view)
    reload()
}
