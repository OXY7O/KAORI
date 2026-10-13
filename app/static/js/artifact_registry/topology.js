// Artifact Registry Dependency Topology (#1692).
// Presentation only: the source of truth is the committed, bounded Python graph.
const $ = (id) => document.getElementById(id)
const canvas = $('registry-topology-canvas')
const form = $('registry-topology-filters')

if (canvas && form) {
    const graphTab = $('registry-topology-view-tab-graph')
    const listTab = $('registry-topology-view-tab-list')
    const graphShell = $('registry-topology-view-panel-graph')
    const canvasShell = $('registry-topology-canvas-shell')
    const listShell = $('registry-topology-view-panel-list')
    const tbody = $('registry-topology-resource-rows')
    const status = $('registry-topology-status')
    const warning = $('registry-topology-warning')
    const errorPanel = $('registry-topology-error')
    const empty = $('registry-topology-empty')
    const inspector = $('registry-topology-inspector')
    const inspectorContent = $('registry-topology-inspector-content')
    const backdrop = $('registry-topology-backdrop')
    const controls = $('registry-topology-controls')
    const controlsClose = $('registry-topology-controls-close')
    const controlsButton = $('registry-topology-controls-button')
    const detailsButton = $('registry-topology-details-button')
    const labelsToggle = $('registry-topology-labels')
    const edgeLabelsToggle = $('registry-topology-edge-labels')
    const groupNamespaceToggle = $('registry-topology-group-namespace')
    const namespaceBoundaries = $('registry-topology-namespace-boundaries')
    const layoutSelect = $('registry-topology-layout')
    const resourceToggles = [...document.querySelectorAll('[data-registry-topology-type]')]
    const relationshipToggles = [...document.querySelectorAll('[data-registry-topology-relationship]')]
    const scopeSummary = $('registry-topology-scope-summary')
    const loading = $('registry-topology-loading')
    const clearFiltersButton = $('registry-topology-clear-filters')
    const close = $('registry-topology-inspector-close')
    const previous = $('registry-topology-prev')
    const next = $('registry-topology-next')
    let cy = null
    let renderer = null
    let payload = { nodes: [], edges: [], bindings: [], summary: {}, evidence: {} }
    let view = new URL(window.location.href).searchParams.get('view') === 'list' ? 'list' : 'graph'
    let listPage = 1
    let controller = null
    let searchTimer = null
    const pageSize = 5
    const filterKeys = ['source_id', 'cluster_id', 'namespace', 'match_type', 'exposure', 'artifact_id', 'q']
    const hasActiveFilters = () => filterKeys.some((key) =>
        Boolean(new FormData(form).get(key)?.toString().trim())
    )
    const syncClearFiltersVisibility = () => {
        if (clearFiltersButton) clearFiltersButton.hidden = !hasActiveFilters()
    }
    const updateFilterUrl = () => {
        const url = new URL(window.location.href)
        const params = new URLSearchParams(new FormData(form))
        for (const key of filterKeys) {
            const value = params.get(key)?.trim()
            if (value) url.searchParams.set(key, value)
            else url.searchParams.delete(key)
        }
        window.history.replaceState({}, '', url)
        syncClearFiltersVisibility()
    }
    const setLoading = (state) => {
        loading?.classList.toggle('htmx-request', state)
        loading?.setAttribute('aria-busy', String(state))
        $('registry-topology-reload').disabled = state
        canvasShell.setAttribute('aria-busy', String(state))
    }

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
    let paneReturnFocus = null
    let activePane = null
    const closePane = () => {
        if (!activePane) return
        controls.classList.add('hidden')
        inspector.classList.add('hidden')
        backdrop.classList.add('hidden')
        controlsButton.setAttribute('aria-expanded', 'false')
        detailsButton.setAttribute('aria-expanded', 'false')
        activePane = null
        if (paneReturnFocus?.isConnected) paneReturnFocus.focus()
    }
    const openPane = (pane) => {
        if (!activePane) paneReturnFocus = document.activeElement
        activePane = pane
        controls.classList.toggle('hidden', pane !== controls)
        inspector.classList.toggle('hidden', pane !== inspector)
        backdrop.classList.remove('hidden')
        controlsButton.setAttribute('aria-expanded', String(pane === controls))
        detailsButton.setAttribute('aria-expanded', String(pane === inspector))
        ;(pane === controls ? controlsClose : close).focus()
    }
    const closeInspector = () => { if (activePane === inspector) closePane() }
    const openInspector = () => openPane(inspector)
    close.addEventListener('click', closePane)
    controlsClose.addEventListener('click', closePane)
    backdrop.addEventListener('click', closePane)
    controlsButton.addEventListener('click', () => {
        if (activePane === controls) closePane()
        else openPane(controls)
    })
    detailsButton.addEventListener('click', () => {
        if (activePane === inspector) closePane()
        else openPane(inspector)
    })
    document.addEventListener('keydown', (event) => {
        if (!activePane) return
        if (event.key === 'Escape') {
            event.preventDefault()
            closePane()
            return
        }
        if (event.key !== 'Tab') return
        const focusables = [...activePane.querySelectorAll('button:not([disabled]), a[href], select:not([disabled]), input:not([disabled]), summary')]
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

    // The inspector follows Kubernetes Topology's canonical Details / Relationships
    // pattern, while preserving Registry-owned identity and confidence evidence.
    let inspectorTab = 'details'
    let highlightedNodeId = null
    const collapsedNodeIds = new Set()
    const typeLabels = {
        artifact: 'Registry Artifact', cluster: 'Cluster', namespace: 'Namespace',
        workload: 'Workload', pod: 'Pod',
    }
    const typeIcons = {
        artifact: 'package', cluster: 'server', namespace: 'layers-3',
        workload: 'boxes', pod: 'circle-dot',
    }
    const relationshipLabels = { runtime_usage: 'Runtime Usage', owns: 'Owns', contains: 'Contains' }
    const cloneInspectorTemplate = (name) =>
        $(`registry-topology-inspector-${name}-template`)?.content?.firstElementChild?.cloneNode(true) || null
    const fill = (root, selector, value) => {
        const target = root?.querySelector(selector)
        if (target) target.textContent = safeLabel(value)
        return target
    }
    const addFields = (parent, fields) => {
        parent.replaceChildren()
        for (const [name, value] of fields) {
            const item = elements('div', 'flex items-start justify-between gap-3 py-2.5')
            item.append(elements('dt', 'min-w-0 text-xs font-normal text-content-muted', name))
            item.append(elements('dd', 'max-w-[65%] break-words text-right text-xs font-medium text-content-primary', safeLabel(value)))
            parent.append(item)
        }
    }
    const selectedNode = (id) => cy?.getElementById(id)
    const selectNodeById = (id, tab = 'details') => {
        const node = selectedNode(id)
        if (!node?.length || !node.visible()) return
        cy.elements().removeClass('kaori-topology-muted')
        const neighborhood = node.closedNeighborhood(':visible')
        cy.elements(':visible').difference(neighborhood).addClass('kaori-topology-muted')
        node.select()
        inspect(node, tab)
        cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 1.05) }, { duration: 220 })
    }
    const drawMiniMap = (pane, node) => {
        const drawing = pane.querySelector('[data-minimap]')
        if (!drawing || !cy || !node?.length || !node.visible()) return
        const all = cy.nodes(':visible')
        if (!all.length) return
        const ctx = drawing.getContext('2d')
        if (!ctx) return
        const width = drawing.width
        const height = drawing.height
        const bounds = all.boundingBox({ includeLabels: false, includeOverlays: false })
        const padding = 17
        const scale = Math.min(
            (width - padding * 2) / Math.max(bounds.w, 1),
            (height - padding * 2) / Math.max(bounds.h, 1)
        )
        const offsetX = (width - bounds.w * scale) / 2
        const offsetY = (height - bounds.h * scale) / 2
        const point = (n) => ({
            x: offsetX + (n.position('x') - bounds.x1) * scale,
            y: offsetY + (n.position('y') - bounds.y1) * scale,
        })
        ctx.clearRect(0, 0, width, height)
        ctx.strokeStyle = token('--kaori-topology-edge-contains', 'CanvasText')
        ctx.globalAlpha = 0.55
        ctx.lineWidth = 1.3
        for (const edge of cy.edges(':visible')) {
            const from = point(edge.source()), to = point(edge.target())
            ctx.beginPath()
            ctx.moveTo(from.x, from.y)
            ctx.lineTo(to.x, to.y)
            ctx.stroke()
        }
        ctx.globalAlpha = 1
        for (const item of all) {
            const p = point(item)
            const domain = visualDomains[item.data('type')] || 'compute'
            ctx.fillStyle = token(`--kaori-topology-domain-${domain}-fill`, 'Canvas')
            ctx.strokeStyle = token(`--kaori-topology-domain-${domain}-border`, 'CanvasText')
            ctx.lineWidth = item.id() === node.id() ? 2.8 : 1.3
            ctx.beginPath()
            ctx.arc(p.x, p.y, item.id() === node.id() ? 5 : 3.2, 0, Math.PI * 2)
            ctx.fill()
            ctx.stroke()
        }
        const center = () => {
            if (view !== 'graph') setView('graph')
            window.requestAnimationFrame(() => cy?.center(node))
        }
        drawing.onclick = center
        drawing.onkeydown = (event) => {
            if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); center() }
        }
    }
    const renderBindingEvidence = (pane, node) => {
        const rows = associatedBindings(node.id())
        if (!rows.length) return
        pane.classList.remove('hidden')
        const title = elements('h5', 'text-xs font-semibold text-content-primary', `Visible Runtime Evidence (${rows.length})`)
        pane.append(title)
        for (const item of rows.slice(0, 10)) {
            const box = elements('div', 'rounded-lg border border-outline-subtle bg-surface-elevated px-3 py-2')
            box.append(elements('p', 'break-words text-xs font-semibold text-content-primary', `${item.cluster} / ${item.namespace}`))
            box.append(elements('p', 'mt-1 break-words text-xs text-content-secondary', `${item.workload} · ${item.pod}`))
            box.append(elements('p', 'mt-1 text-xs text-content-muted', `${item.match} · ${item.security}`))
            pane.append(box)
        }
        if (rows.length > 10) pane.append(elements('p', 'text-xs text-content-muted', `${rows.length - 10} additional visible bindings; refine scope or use Runtime Usage.`))
    }
    const renderRelationshipRows = (target, node) => {
        target.replaceChildren()
        const edges = node.connectedEdges(':visible')
        if (!edges.length) {
            target.append(elements('p', 'rounded-xl border border-dashed border-outline-strong bg-kaori-soft p-6 text-center text-xs font-medium text-kaori-primary', 'No Visible Relationships'))
            return
        }
        edges.forEach((edge) => {
            const outbound = edge.source().id() === node.id()
            const peer = outbound ? edge.target() : edge.source()
            const row = cloneInspectorTemplate('relationship-row')
            if (!row) return
            fill(row, '[data-edge-direction]', outbound ? 'Outbound' : 'Inbound')
            fill(row, '[data-edge-relationship]', relationshipLabels[edge.data('relationship')] || edge.data('relationship'))
            fill(row, '[data-peer-label]', peer.data('label'))
            fill(row, '[data-peer-type]', typeLabels[peer.data('type')] || peer.data('type'))
            row.addEventListener('click', () => selectNodeById(peer.id(), 'relationships'))
            target.append(row)
        })
        window.lucide?.createIcons()
    }
    const inspect = (node, initialTab = inspectorTab) => {
        const data = node.data()
        const pane = cloneInspectorTemplate('node')
        if (!pane) return
        const badge = pane.querySelector('[data-node-icon-shell]')
        badge?.classList.add(`kaori-topology-domain-${visualDomains[data.type] || 'compute'}`)
        pane.querySelector('[data-node-icon]')?.setAttribute('data-lucide', typeIcons[data.type] || 'box')
        fill(pane, '[data-node-label]', data.label)
        fill(pane, '[data-node-kind]', data.subtitle || typeLabels[data.type] || data.type)
        fill(pane, '[data-node-type]', typeLabels[data.type] || data.type)
        const evidence = payload.evidence || {}
        fill(pane, '[data-node-evidence]', data.type === 'artifact' ? (data.security || 'Scan Evidence Unknown') : (evidence.title || 'Committed Scope'))
        fill(pane, '[data-node-description]', data.type === 'artifact'
            ? 'Authoritative Registry artifact identity and reported scan posture.'
            : 'Resource context derived from committed Registry-to-Kubernetes runtime bindings.')
        const fields = []
        if (data.type === 'artifact') {
            fields.push(['Registry Source', data.source], ['Digest', data.digest],
                ['Scan Status', data.scan_status], ['Critical / High', `${data.critical ?? 0} / ${data.high ?? 0}`])
        } else if (data.type === 'cluster') {
            fields.push(['Kubernetes Cluster', data.label], ['Cluster Identity', data.cluster_id])
        } else {
            fields.push(['Resource', data.label], ['Type', typeLabels[data.type] || data.type])
            const row = associatedBindings(node.id())[0]
            if (row) {
                fields.push(['Cluster', row.cluster], ['Namespace', row.namespace],
                    ['Workload', row.workload], ['Pod', row.pod],
                    ['Match Type', row.match], ['Confidence', row.confidence])
            }
        }
        fields.push(['Correlation Readiness', evidence.title || evidence.status || 'Unknown'])
        addFields(pane.querySelector('[data-node-fields]'), fields)
        const edges = node.connectedEdges(':visible')
        if (edges.length) {
            pane.querySelector('[data-relationship-summary]')?.classList.remove('hidden')
            const counts = new Map()
            edges.forEach((edge) => {
                const outbound = edge.source().id() === node.id()
                const key = `${edge.data('relationship')}:${outbound ? 'out' : 'in'}`
                counts.set(key, (counts.get(key) || 0) + 1)
            })
            const summary = pane.querySelector('[data-relationship-summary-items]')
            for (const [key, count] of counts) {
                const [relationship, direction] = key.split(':')
                const chip = elements('span', 'inline-flex min-h-7 items-center gap-1.5 rounded-md border border-outline-subtle bg-surface-card px-2 py-1 text-xs font-medium text-content-secondary', `${relationshipLabels[relationship] || relationship} · ${direction === 'out' ? 'Outbound' : 'Inbound'} · ${count}`)
                chip.setAttribute('role', 'listitem')
                summary.append(chip)
            }
        }
        const descendants = node.successors('node').filter(':visible')
        const collapsed = collapsedNodeIds.has(node.id())
        const collapseButton = pane.querySelector('[data-collapse-path]')
        collapseButton.disabled = !descendants.length && !collapsed
        fill(pane, '[data-collapse-label]', descendants.length ? (collapsed ? `Expand ${descendants.length}` : `Collapse ${descendants.length}`) : collapsed ? 'Expand Children' : 'No Loaded Children')
        collapseButton.addEventListener('click', () => {
            if (collapsed) collapsedNodeIds.delete(node.id())
            else collapsedNodeIds.add(node.id())
            applyVisibility()
            runLayout()
            inspect(node, inspectorTab)
        })
        fill(pane, '[data-highlight-label]', highlightedNodeId === node.id() ? 'Clear Path' : 'Highlight Path')
        pane.querySelector('[data-highlight-path]').addEventListener('click', () => {
            if (highlightedNodeId === node.id()) {
                highlightedNodeId = null
                cy.elements().removeClass('kaori-topology-muted')
            } else {
                highlightedNodeId = node.id()
                const related = node.union(node.predecessors()).union(node.closedNeighborhood(':visible'))
                cy.elements(':visible').addClass('kaori-topology-muted')
                related.removeClass('kaori-topology-muted')
            }
            inspect(node, inspectorTab)
        })
        const action = pane.querySelector('[data-node-action]')
        if (data.url) {
            action.href = data.url
            action.classList.remove('hidden')
            action.classList.add('inline-flex')
        }
        const runtime = pane.querySelector('[data-node-runtime-bindings]')
        renderBindingEvidence(runtime, node)
        if (data.type === 'artifact' || data.type === 'cluster') {
            pane.querySelector('[data-node-minimap]')?.classList.remove('hidden')
        }
        const tabs = [...pane.querySelectorAll('[data-kaori-segmented-tab]')]
        const detailsPanel = pane.querySelector('#registry-topology-inspector-panel-details')
        const relationshipsPanel = pane.querySelector('#registry-topology-inspector-panel-relationships')
        const activate = (chosen) => {
            inspectorTab = chosen === 'relationships' ? 'relationships' : 'details'
            tabs.forEach((tab) => {
                const active = tab.dataset.kaoriSegmentedTab === inspectorTab
                tab.setAttribute('aria-selected', String(active))
                tab.tabIndex = active ? 0 : -1
                tab.classList.toggle('bg-surface-card', active)
                tab.classList.toggle('text-kaori-primary', active)
                tab.classList.toggle('shadow-sm', active)
                tab.classList.toggle('text-content-muted', !active)
            })
            detailsPanel.hidden = inspectorTab !== 'details'
            relationshipsPanel.hidden = inspectorTab !== 'relationships'
            if (inspectorTab === 'relationships') renderRelationshipRows(relationshipsPanel.querySelector('[data-node-relationships]'), node)
            else window.requestAnimationFrame(() => drawMiniMap(pane, node))
        }
        tabs.forEach((tab) => {
            tab.addEventListener('click', () => activate(tab.dataset.kaoriSegmentedTab))
            tab.addEventListener('keydown', (event) => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
                event.preventDefault()
                const next = tab.dataset.kaoriSegmentedTab === 'details' ? 'relationships' : 'details'
                activate(next)
                tabs.find((t) => t.dataset.kaoriSegmentedTab === next)?.focus()
            })
        })
        pane.querySelector('[data-open-relationships]')?.addEventListener('click', () => activate('relationships'))
        inspectorContent.replaceChildren(pane)
        openInspector()
        activate(initialTab)
        window.lucide?.createIcons()
    }
    const inspectBinding = (item) => {
        const node = selectedNode(item.node_id)
        if (node?.length) {
            selectNodeById(node.id())
            return
        }
        // Data can still be inspected when the graph renderer fails.
        inspectorContent.replaceChildren()
        const box = elements('dl', 'divide-y divide-outline-subtle rounded-xl border border-outline-subtle bg-surface-card px-3')
        addFields(box, [
            ['Artifact', item.artifact], ['Registry Source', item.source],
            ['Cluster', item.cluster], ['Namespace', item.namespace],
            ['Workload', item.workload], ['Pod', item.pod],
            ['Match', item.match], ['Confidence', item.confidence],
            ['Security', item.security], ['Observed At', item.observed_at],
        ])
        inspectorContent.append(box, link('Open Runtime Usage', item.url))
        openInspector()
    }

    const graphParents = () => {
        const parents = new Map()
        for (const edge of payload.edges) parents.set(edge.data.target, edge.data.source)
        return parents
    }
    const resourceScope = (item, parents, byId) => {
        let cursor = item.data.id
        let cluster = item.data.type === 'cluster' ? item.data.label : null
        let namespace = item.data.type === 'namespace' ? item.data.label : null
        let counter = 0
        while (parents.has(cursor) && counter++ < 7) {
            const ancestor = byId.get(parents.get(cursor))
            if (!ancestor) break
            if (ancestor.data.type === 'cluster') cluster = ancestor.data.label
            if (ancestor.data.type === 'namespace') namespace = ancestor.data.label
            cursor = ancestor.data.id
        }
        return {
            cluster: cluster || (item.data.type === 'artifact' ? 'Cross Cluster' : 'Not Reported'),
            namespace: namespace || 'Cluster Scoped',
        }
    }
    const inspectResource = (item) => {
        const node = selectedNode(item.data.id)
        if (node?.length) {
            selectNodeById(item.data.id)
            return
        }
        const details = elements('dl', 'divide-y divide-outline-subtle rounded-xl border border-outline-subtle bg-surface-card px-3')
        addFields(details, [['Resource', item.data.label], ['Type', typeLabels[item.data.type] || item.data.type],
            ['Evidence', payload.evidence?.title || 'Unknown'], ['Snapshot Scope', 'Committed / Bounded']])
        inspectorContent.replaceChildren(details)
        openInspector()
    }
    const renderList = () => {
        tbody.replaceChildren()
        // Render graph resources (not binding-only rows), matching K8s Inventory.
        const nodes = payload.nodes.filter((node) =>
            resourceToggles.find((toggle) => toggle.dataset.registryTopologyType === node.data.type)?.checked !== false &&
            (!cy || cy.$id(node.data.id).visible())
        )
        const byId = new Map(payload.nodes.map((node) => [node.data.id, node]))
        const parents = graphParents()
        const total = nodes.length
        const maxPage = Math.max(Math.ceil(total / pageSize), 1)
        listPage = Math.min(Math.max(listPage, 1), maxPage)
        const page = nodes.slice((listPage - 1) * pageSize, listPage * pageSize)
        for (const item of page) {
            const data = item.data
            const scope = resourceScope(item, parents, byId)
            const kind = typeLabels[data.type] || data.type
            const tr = elements('tr', 'border-b border-outline-subtle')
            const nameCell = elements('td', 'px-4 py-3 text-sm font-medium text-content-primary')
            const identity = elements('div', 'flex min-w-0 items-center gap-3')
            const badge = elements('span',
                `flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-xs font-bold kaori-topology-domain-${visualDomains[data.type] || 'compute'}`,
                glyphs[data.type] || 'RS'
            )
            const labels = elements('div', 'min-w-0')
            labels.append(elements('p', 'break-words text-xs font-semibold text-content-primary', data.label))
            labels.append(elements('p', 'text-xs text-content-muted', data.subtitle || kind))
            identity.append(badge, labels)
            nameCell.append(identity)
            const typeCell = elements('td', 'px-4 py-3 text-xs text-content-secondary', kind)
            const clusterCell = elements('td', 'px-4 py-3 text-xs text-content-secondary', scope.cluster)
            const namespaceCell = elements('td', 'px-4 py-3 text-xs text-content-secondary', scope.namespace)
            const evidenceCell = elements('td', 'px-4 py-3 text-xs text-content-secondary')
            evidenceCell.append(elements('span', 'inline-flex min-h-6 items-center rounded-md bg-status-unknown-soft px-2 text-xs font-medium text-status-unknown-text',
                data.type === 'artifact' ? (data.security || 'Scan Unknown') : (payload.evidence?.title || 'Committed Evidence')))
            const count = payload.edges.filter((edge) => edge.data.source === data.id || edge.data.target === data.id).length
            const relationshipCell = elements('td', 'px-4 py-3 text-xs font-semibold text-content-primary', count)
            const detailsCell = elements('td', 'px-4 py-3 text-right')
            const button = elements('button', 'rounded-lg border border-outline-default px-3 py-2 text-xs font-semibold text-kaori-primary hover:bg-kaori-soft', 'View Details')
            button.type = 'button'
            button.addEventListener('click', () => inspectResource(item))
            detailsCell.append(button)
            tr.append(nameCell, typeCell, clusterCell, namespaceCell, evidenceCell, relationshipCell, detailsCell)
            tbody.append(tr)
        }
        if (!page.length) {
            const row = elements('tr')
            const cell = elements('td', 'px-4 py-8 text-center text-sm text-content-muted',
                'No visible resources. Review filters and committed correlation readiness.')
            cell.colSpan = 7
            row.append(cell)
            tbody.append(row)
        }
        $('registry-topology-list-count').textContent =
            `Showing ${page.length ? (listPage - 1) * pageSize + 1 : 0}–${(listPage - 1) * pageSize + page.length} of ${total} visible resources (from ${payload.summary.displayed_bindings ?? 0} displayed bindings; ${payload.summary.omitted_bindings ?? 0} omitted).`
        previous.disabled = listPage <= 1
        next.disabled = listPage >= maxPage
    }

    let graphHasLayout = false
    const setView = (value) => {
        view = value
        const graphVisible = value === 'graph'
        graphShell.hidden = !graphVisible
        listShell.hidden = graphVisible
        graphShell.classList.toggle('hidden', !graphVisible)
        listShell.classList.toggle('hidden', graphVisible)
        for (const [tab, active] of [[graphTab, graphVisible], [listTab, !graphVisible]]) {
            tab.setAttribute('aria-selected', String(active))
            tab.tabIndex = active ? 0 : -1
            tab.classList.toggle('bg-surface-card', active)
            tab.classList.toggle('text-kaori-primary', active)
            tab.classList.toggle('shadow-sm', active)
            tab.classList.toggle('text-content-muted', !active)
        }
        for (const id of ['registry-topology-fit', 'registry-topology-reset', 'registry-topology-export']) {
            $(id).disabled = !graphVisible || !cy
        }
        const url = new URL(window.location.href)
        if (graphVisible) url.searchParams.delete('view')
        else url.searchParams.set('view', 'list')
        window.history.replaceState({}, '', url)
        if (graphVisible && cy) {
            window.requestAnimationFrame(() => {
                cy.resize()
                if (!graphHasLayout) runLayout()
                else fitGraph()
                scheduleNamespaceBoundaries()
            })
        }
    }
    graphTab.addEventListener('click', () => setView('graph'))
    listTab.addEventListener('click', () => setView('list'))
    for (const [tab, value, other] of [[graphTab, 'graph', listTab], [listTab, 'list', graphTab]]) {
        tab.addEventListener('keydown', (event) => {
            if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return
            event.preventDefault()
            setView(value === 'graph' ? 'list' : 'graph')
            other.focus()
        })
    }
    previous.addEventListener('click', () => { listPage -= 1; renderList() })
    next.addEventListener('click', () => { listPage += 1; renderList() })

    // Match Kubernetes Inventory Topology's small domain badge + external label
    // instead of long centered text inside oversized rectangle nodes.
    const visualDomains = {
        artifact: 'configuration',
        cluster: 'scope',
        namespace: 'scope',
        workload: 'compute',
        pod: 'compute',
    }
    const glyphs = { artifact: 'AR', cluster: 'CL', namespace: 'NS', workload: 'WL', pod: 'PD' }
    const badgeCache = new Map()
    const nodeVisual = (type) => {
        const domain = visualDomains[type] || 'compute'
        return {
            fill: token(`--kaori-topology-domain-${domain}-fill`, 'Canvas'),
            border: token(`--kaori-topology-domain-${domain}-border`, 'CanvasText'),
            text: token(`--kaori-topology-domain-${domain}-text`, 'CanvasText'),
        }
    }
    const nodeTone = (data) => {
        if (data.type !== 'artifact') return 'unknown'
        if (Number(data.critical) > 0) return 'critical'
        if (Number(data.high) > 0) return 'warning'
        // A scan with zero high findings is not evidence of healthy runtime.
        return 'unknown'
    }
    const badgeImage = (data) => {
        const visual = nodeVisual(data.type)
        const tone = nodeTone(data)
        const statusColor = token(`--kaori-status-${tone === 'critical' ? 'critical' : tone === 'warning' ? 'warning' : 'unknown'}`, 'CanvasText')
        const outline = token('--kaori-surface-card', 'Canvas')
        const glyph = glyphs[data.type] || 'RS'
        const key = [data.type, tone, visual.text, statusColor, outline].join(':')
        if (badgeCache.has(key)) return badgeCache.get(key)
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="52" viewBox="0 0 96 52"><text x="48" y="32" text-anchor="middle" font-family="Inter, sans-serif" font-size="16" font-weight="700" fill="${visual.text}">${glyph}</text><circle cx="84" cy="10" r="5" fill="${statusColor}" stroke="${outline}" stroke-width="2"/></svg>`
        const result = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
        badgeCache.set(key, result)
        return result
    }
    const displayLabel = (value) => {
        const label = String(value || 'Not Reported')
        return label.length > 30 ? `${label.slice(0, 29)}…` : label
    }
    const graphStyle = () => {
        const surface = token('--kaori-surface-card', 'Canvas')
        const foreground = token('--kaori-content-primary', 'CanvasText')
        const contains = token('--kaori-topology-edge-contains', 'CanvasText')
        const owns = token('--kaori-topology-edge-owns', 'CanvasText')
        const uses = token('--kaori-topology-edge-uses', 'CanvasText')
        const warningColor = token('--kaori-status-warning', 'CanvasText')
        return [
            {
                selector: 'node',
                style: {
                    'background-color': (node) => nodeVisual(node.data('type')).fill,
                    'border-color': (node) => nodeVisual(node.data('type')).border,
                    'border-width': 2,
                    shape: 'round-rectangle',
                    height: 44,
                    width: 76,
                    padding: 0,
                    'background-image': (node) => badgeImage(node.data()),
                    'background-width': '100%',
                    'background-height': '100%',
                    'background-position-x': '50%',
                    'background-position-y': '50%',
                    'background-repeat': 'no-repeat',
                    'background-fit': 'none',
                    'background-image-containment': 'inside',
                    label: labelsToggle.checked ? 'data(display_label)' : '',
                    color: foreground,
                    'font-family': 'Inter, sans-serif',
                    'font-size': 10,
                    'font-weight': 600,
                    'text-valign': 'bottom',
                    'text-halign': 'center',
                    'text-justification': 'center',
                    'text-wrap': 'ellipsis',
                    'text-max-width': 195,
                    'text-margin-y': 11,
                    'text-background-color': surface,
                    'text-background-opacity': 0.94,
                    'text-background-padding': 3,
                    'text-background-shape': 'roundrectangle',
                    'text-border-color': token('--kaori-outline-subtle', 'GrayText'),
                    'text-border-width': 1,
                    'text-border-opacity': 0.8,
                    'overlay-opacity': 0,
                    'shadow-blur': 10,
                    'shadow-color': foreground,
                    'shadow-offset-x': 0,
                    'shadow-offset-y': 3,
                    'shadow-opacity': 0.1,
                },
            },
            {
                selector: 'node[type = "artifact"]',
                style: { width: 96, height: 52, 'font-size': 11, 'font-weight': 700 },
            },
            {
                selector: 'node[type = "cluster"]',
                style: { width: 92, height: 48, 'font-weight': 700 },
            },
            {
                selector: 'edge',
                style: {
                    'curve-style': 'bezier',
                    'line-color': (edge) => {
                        const kind = edge.data('relationship')
                        if (kind === 'contains') return contains
                        if (kind === 'owns') return owns
                        return ['medium', 'mixed'].includes(edge.data('confidence')) ? warningColor : uses
                    },
                    'line-opacity': 0.78,
                    'line-style': (edge) => edge.data('relationship') === 'contains' ? 'dashed' : 'solid',
                    'target-arrow-shape': (edge) => edge.data('relationship') === 'contains' ? 'none' : 'triangle',
                    'target-arrow-color': (edge) => {
                        if (edge.data('relationship') === 'owns') return owns
                        return ['medium', 'mixed'].includes(edge.data('confidence')) ? warningColor : uses
                    },
                    'arrow-scale': 0.78,
                    width: 2,
                    label: '',
                    'font-family': 'Inter, sans-serif',
                    'font-size': 9,
                    'font-weight': 600,
                    color: foreground,
                    'text-rotation': 'none',
                    'text-background-color': surface,
                    'text-background-opacity': 0.96,
                    'text-background-padding': 3,
                    'text-background-shape': 'roundrectangle',
                    'text-border-color': token('--kaori-outline-subtle', 'GrayText'),
                    'text-border-width': 1,
                    'text-border-opacity': 0.7,
                    'overlay-opacity': 0,
                },
            },
            {
                selector: 'edge[relationship = "contains"]',
                style: {
                    'curve-style': 'taxi',
                    'taxi-direction': 'horizontal',
                    'taxi-turn': 24,
                    'line-style': 'dashed',
                    'line-opacity': 0.38,
                    'target-arrow-shape': 'none',
                    width: 1,
                },
            },
            {
                selector: 'edge.edge-label-visible',
                style: {
                    label: (edge) => edge.data('relationship') === 'runtime_usage'
                        ? 'used at runtime' : edge.data('relationship') === 'owns' ? 'owns' : 'contains',
                },
            },
            {
                selector: 'edge.edge-hovered',
                style: {
                    width: 3,
                    'line-color': token('--kaori-brand-primary', 'CanvasText'),
                    'target-arrow-color': token('--kaori-brand-primary', 'CanvasText'),
                    'line-opacity': 1,
                },
            },
            { selector: 'node:selected', style: { 'border-width': 3, 'border-color': token('--kaori-brand-primary', 'CanvasText') } },
            { selector: '.kaori-topology-muted', style: { opacity: 0.16 } },
        ]
    }
    const layoutOptions = () => {
        const displayed = cy ? cy.nodes(':visible').length : payload.nodes.length
        if (layoutSelect.value === 'dependency') {
            return {
                name: 'cose',
                animate: 'end',
                animationDuration: 420,
                fit: true,
                nodeDimensionsIncludeLabels: true,
                padding: 80,
                idealEdgeLength: 175,
                nodeRepulsion: 620000,
                gravity: 0.3,
                componentSpacing: 145,
                numIter: 1200,
                randomize: false,
            }
        }
        const hasBranches = cy.edges(':visible').reduce((counts, edge) => {
            const id = edge.source().id()
            counts.set(id, (counts.get(id) || 0) + 1)
            return counts
        }, new Map())
        const branched = [...hasBranches.values()].some((count) => count > 1)
        return {
            name: 'breadthfirst',
            directed: true,
            circle: false,
            grid: true,
            roots: cy.nodes('[type = "artifact"]').filter(':visible'),
            animate: false,
            nodeDimensionsIncludeLabels: true,
            padding: displayed <= 8 ? 72 : 64,
            spacingFactor: displayed <= 8 ? 1.18 : displayed <= 35 ? 1.48 : 1.88,
            // Match Kubernetes top-down trees when branches exist. Only a
            // single-chain evidence path is rotated to use canvas width.
            transform: (_node, position) => branched ? position : ({ x: position.y, y: position.x }),
        }
    }
    const fitGraph = () => {
        if (!cy || !cy.nodes(':visible').length || view !== 'graph') return
        cy.resize()
        const rect = canvas.getBoundingClientRect()
        if (rect.width < 120 || rect.height < 120) return
        const nodes = cy.nodes(':visible')
        const edges = cy.edges(':visible')
        const bbox = nodes.union(edges).boundingBox({ includeLabels: true, includeOverlays: false })
        const padding = Math.max(48, Math.min(88, Math.round(Math.min(rect.width, rect.height) * 0.08)))
        cy.fit(bbox, padding)
        // Cap over-magnification of small graphs while keeping them centered.
        if (cy.zoom() > 1.6) cy.zoom({ level: 1.6, renderedPosition: { x: rect.width / 2, y: rect.height / 2 } })
    }
    const applyVisibility = () => {
        if (!cy) return
        const enabled = Object.fromEntries(resourceToggles.map((toggle) => [toggle.dataset.registryTopologyType, toggle.checked]))
        const relationships = Object.fromEntries(relationshipToggles.map((toggle) => [toggle.dataset.registryTopologyRelationship, toggle.checked]))
        cy.nodes().forEach((node) => {
            const ancestorsCollapsed = node.predecessors('node').some((item) => collapsedNodeIds.has(item.id()))
            node.style('display', enabled[node.data('type')] && !ancestorsCollapsed ? 'element' : 'none')
        })
        cy.edges().forEach((edge) => {
            const included = edge.source().visible() &&
                edge.target().visible() &&
                relationships[edge.data('relationship')]
            edge.style('display', included ? 'element' : 'none')
        })
        if (view === 'list') renderList()
        scheduleNamespaceBoundaries()
    }
    const runLayout = () => {
        if (!cy) return
        applyVisibility()
        const visible = cy.elements(':visible')
        if (!visible.nodes().length) return
        const layout = visible.layout(layoutOptions())
        layout.one('layoutstop', () => {
            graphHasLayout = true
            window.requestAnimationFrame(() => {
                fitGraph()
                scheduleNamespaceBoundaries()
                window.setTimeout(fitGraph, 130)
            })
        })
        layout.run()
    }
    let boundaryFrame = null
    const updateNamespaceBoundaries = () => {
        boundaryFrame = null
        if (!namespaceBoundaries) return
        namespaceBoundaries.replaceChildren()
        if (!cy || !groupNamespaceToggle?.checked || view !== 'graph') return
        for (const scope of cy.nodes('[type = "namespace"]:visible')) {
            const related = scope.union(scope.successors('node:visible'))
            if (related.length < 2) continue
            const box = related.renderedBoundingBox({ includeLabels: true, includeOverlays: false })
            if (!Number.isFinite(box.x1) || box.w < 1 || box.h < 1) continue
            const marginX = 16, marginY = 22
            const overlay = elements('div', 'absolute rounded-xl border border-dashed border-kaori-primary/25 bg-kaori-soft/10')
            overlay.style.left = `${Math.max(0, box.x1 - marginX)}px`
            overlay.style.top = `${Math.max(0, box.y1 - marginY)}px`
            overlay.style.width = `${box.w + marginX * 2}px`
            overlay.style.height = `${box.h + marginY * 2}px`
            overlay.title = `Namespace: ${scope.data('label')}`
            namespaceBoundaries.append(overlay)
        }
    }
    const scheduleNamespaceBoundaries = () => {
        if (boundaryFrame !== null) return
        boundaryFrame = window.requestAnimationFrame(updateNamespaceBoundaries)
    }
    const updateEdgeLabelClasses = () => {
        if (!cy) return
        cy.edges().forEach((edge) => {
            edge.toggleClass('edge-label-visible', edgeLabelsToggle.checked || edge.selected() || edge.hasClass('edge-hovered'))
        })
    }
    const renderGraph = async () => {
        if (!renderer) {
            const module = await import(canvas.dataset.rendererUrl)
            renderer = module.c || module.default
            if (typeof renderer !== 'function') throw new Error('Cytoscape module is unavailable')
        }
        if (cy) cy.destroy()
        const records = payload.nodes.map((node) => ({
            ...node,
            data: { ...node.data, display_label: displayLabel(node.data.label) },
        }))
        cy = renderer({
            container: canvas,
            elements: [...records, ...payload.edges],
            layout: { name: 'preset' },
            minZoom: 0.12,
            maxZoom: 2.6,
            pixelRatio: 'auto',
            selectionType: 'single',
            style: graphStyle(),
        })
        const tip = $('registry-topology-node-tooltip')
        const hideTip = () => tip?.classList.add('hidden')
        cy.on('mouseover', 'node', (event) => {
            if (!tip) return
            const node = event.target
            tip.textContent = `${node.data('type')} · ${node.data('label')}`
            tip.classList.remove('hidden')
            const at = node.renderedPosition()
            tip.style.left = `${Math.max(12, Math.min(canvas.clientWidth - Math.min(tip.offsetWidth, 300) - 12, at.x + 15))}px`
            tip.style.top = `${Math.max(8, Math.min(canvas.clientHeight - 52, at.y - 36))}px`
        })
        cy.on('mouseout', 'node', hideTip)
        cy.on('pan zoom', hideTip)
        cy.on('pan zoom resize position layoutstop', scheduleNamespaceBoundaries)
        cy.on('mouseover', 'edge', (event) => {
            event.target.addClass('edge-hovered')
            updateEdgeLabelClasses()
        })
        cy.on('mouseout', 'edge', (event) => {
            event.target.removeClass('edge-hovered')
            updateEdgeLabelClasses()
        })
        cy.on('tap', 'node', (event) => {
            hideTip()
            const node = event.target
            cy.elements().removeClass('kaori-topology-muted')
            const neighborhood = node.closedNeighborhood().union(node)
            cy.elements().difference(neighborhood).addClass('kaori-topology-muted')
            inspect(node)
        })
        cy.on('tap', (event) => {
            if (event.target === cy) {
                cy.elements().removeClass('kaori-topology-muted')
                hideTip()
                cy.elements().unselect()
                updateEdgeLabelClasses()
            }
        })
        cy.on('tap', 'edge', (event) => {
            const edge = event.target
            edge.select()
            updateEdgeLabelClasses()
            const pane = cloneInspectorTemplate('edge')
            if (!pane) return
            addFields(pane.querySelector('[data-edge-fields]'), [
                ['Relationship', relationshipLabels[edge.data('relationship')] || edge.data('relationship')],
                ['From', edge.source().data('label')],
                ['To', edge.target().data('label')],
                ['Match Confidence', edge.data('confidence') || 'Structural context'],
                ['Evidence Readiness', payload.evidence?.title || 'Unknown'],
            ])
            inspectorContent.replaceChildren(pane)
            openInspector()
            window.lucide?.createIcons()
        })
        updateEdgeLabelClasses()
        graphHasLayout = false
        setView(view)
    }

    const reload = async () => {
        if (controller) controller.abort()
        const requestController = new AbortController()
        controller = requestController
        setLoading(true)
        status.classList.remove('hidden')
        status.textContent = 'Loading committed dependency evidence…'
        warning.classList.add('hidden')
        errorPanel.classList.add('hidden')
        closePane()
        const params = new URLSearchParams(new FormData(form))
        const dataUrl = new URL(canvas.dataset.url, window.location.origin)
        dataUrl.search = params.toString()
        try {
            const response = await fetch(dataUrl, {
                headers: { Accept: 'application/json' },
                signal: requestController.signal,
                credentials: 'same-origin',
            })
            if (!response.ok) throw new Error(`Graph request failed (HTTP ${response.status})`)
            payload = await response.json()
            highlightedNodeId = null
            collapsedNodeIds.clear()
            if (cy) { cy.destroy(); cy = null }
            for (const typeToggle of resourceToggles) {
                const count = payload.nodes.filter((node) => node.data.type === typeToggle.dataset.registryTopologyType).length
                const countNode = document.querySelector(`[data-registry-topology-type-count="${typeToggle.dataset.registryTopologyType}"]`)
                if (countNode) countNode.textContent = String(count)
            }
            listPage = 1
            renderList()
            const summary = payload.summary
            const evidence = payload.evidence
            scopeSummary.textContent = `${summary.artifacts_visible} artifacts · ${summary.workloads_visible} workloads · ${summary.pods_visible} pods · ${summary.displayed_bindings}/${summary.total_bindings} bindings · ${evidence.title}`
            status.classList.add('hidden')
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
            status.classList.add('hidden')
            scopeSummary.textContent = 'Topology unavailable — no evidence conclusion can be drawn.'
        } finally {
            // Abort from an older request cannot dismiss a newer request's bar.
            if (controller === requestController) setLoading(false)
        }
    }

    const commitFilterChange = () => {
        updateFilterUrl()
        reload()
    }
    form.addEventListener('submit', (event) => {
        event.preventDefault()
        window.clearTimeout(searchTimer)
        commitFilterChange()
    })
    form.querySelectorAll('select').forEach((select) =>
        select.addEventListener('change', commitFilterChange)
    )
    form.querySelector('input[name="q"]')?.addEventListener('input', () => {
        window.clearTimeout(searchTimer)
        searchTimer = window.setTimeout(commitFilterChange, 350)
    })
    clearFiltersButton?.addEventListener('click', (event) => {
        event.preventDefault()
        window.clearTimeout(searchTimer)
        form.querySelectorAll('select').forEach((select) => { select.selectedIndex = 0 })
        form.querySelector('input[name="q"]').value = ''
        form.querySelector('input[name="artifact_id"]')?.remove()
        commitFilterChange()
    })
    $('registry-topology-reload').addEventListener('click', reload)
    $('registry-topology-fit').addEventListener('click', fitGraph)
    $('registry-topology-reset').addEventListener('click', () => {
        if (!cy) return
        cy.elements().removeClass('kaori-topology-muted')
        graphHasLayout = false
        runLayout()
    })
    const updateDisplay = (relayout = false) => {
        if (!cy) return
        cy.style().fromJson(graphStyle()).update()
        updateEdgeLabelClasses()
        cy.elements().removeClass('kaori-topology-muted')
        if (relayout) {
            graphHasLayout = false
            runLayout()
        } else fitGraph()
    }
    groupNamespaceToggle?.addEventListener('change', scheduleNamespaceBoundaries)
    labelsToggle.addEventListener('change', () => updateDisplay())
    edgeLabelsToggle.addEventListener('change', () => updateDisplay())
    layoutSelect.addEventListener('change', () => {
        const url = new URL(window.location.href)
        if (layoutSelect.value === 'dependency') url.searchParams.set('layout', 'dependency')
        else url.searchParams.delete('layout')
        window.history.replaceState({}, '', url)
        updateDisplay(true)
    })
    relationshipToggles.forEach((toggle) => toggle.addEventListener('change', () => updateDisplay(true)))
    resourceToggles.forEach((toggle) => toggle.addEventListener('change', () => {
        if (!cy) return
        applyVisibility()
        empty.classList.toggle('hidden', cy.nodes(':visible').length > 0)
        empty.classList.toggle('flex', cy.nodes(':visible').length === 0)
        updateDisplay(true)
    }))
    $('registry-topology-export').addEventListener('click', () => {
        if (!cy) return
        const output = cy.png({
            full: true,
            scale: 2,
            bg: token('--kaori-surface-card', 'Canvas'),
        })
        const anchor = document.createElement('a')
        anchor.href = output
        anchor.download = 'kaori-artifact-dependency-topology.png'
        anchor.click()
    })
    $('registry-topology-export-json').addEventListener('click', () => {
        const bytes = JSON.stringify({
            ...payload,
            export_scope: 'bounded committed graph slice; omitted records are not negative evidence',
        }, null, 2)
        const objectUrl = URL.createObjectURL(new Blob([bytes], { type: 'application/json' }))
        const anchor = document.createElement('a')
        anchor.href = objectUrl
        anchor.download = 'kaori-artifact-dependency-topology.json'
        anchor.click()
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    })
    const initialLayout = new URL(window.location.href).searchParams.get('layout')
    layoutSelect.value = initialLayout === 'dependency' ? 'dependency' : 'hierarchy'
    setView(view)
    syncClearFiltersVisibility()
    reload()
}
