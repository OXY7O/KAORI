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
    let cy = null
    let renderer = null
    let payload = { nodes: [], edges: [], bindings: [], summary: {}, evidence: {} }
    let view = new URL(window.location.href).searchParams.get('view') === 'list' ? 'list' : 'graph'
    let controller = null
    let searchTimer = null
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
    const renderEmptyInspector = () => {
        const emptyPane = cloneInspectorTemplate('empty')
        if (emptyPane) inspectorContent.replaceChildren(emptyPane)
        window.lucide?.createIcons()
    }
    const fill = (root, selector, value) => {
        const target = root?.querySelector(selector)
        if (target) target.textContent = safeLabel(value)
        return target
    }
    const addFields = (parent, fields) => {
        if (!parent) return
        parent.replaceChildren()
        for (const [name, value] of fields) {
            const item = $('registry-topology-field-row-template')?.content.firstElementChild?.cloneNode(true)
            if (!item) continue
            fill(item, '[data-field-label]', name)
            fill(item, '[data-field-value]', value)
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
    let drawerMiniMapFrame = null
    let selectedMiniMapNodeId = null
    const drawMiniMap = () => {
        drawerMiniMapFrame = null
        if (!cy || activePane !== inspector || inspectorTab !== 'details' || !selectedMiniMapNodeId) return
        const drawing = inspectorContent.querySelector('[data-minimap]')
        const node = cy.getElementById(selectedMiniMapNodeId)
        if (!drawing || !node?.length || !node.visible()) return
        // K8s topology mini-map convention: show the selected rooted branch
        // rather than a single selected badge or the entire unrelated fleet.
        const nodes = node.union(node.successors('node')).filter(':visible')
        const nodeIds = new Set(nodes.map((item) => item.id()))
        const edges = cy.edges(':visible').filter((edge) =>
            nodeIds.has(edge.source().id()) && nodeIds.has(edge.target().id())
        )
        const section = drawing.closest('[data-node-minimap]')
        if (nodes.length < 2 || !edges.length) {
            section?.classList.add('hidden')
            return
        }
        section?.classList.remove('hidden')
        const width = Math.max(180, drawing.clientWidth || 220)
        const height = 144
        const pixelRatio = Math.max(1, window.devicePixelRatio || 1)
        drawing.width = Math.round(width * pixelRatio)
        drawing.height = Math.round(height * pixelRatio)
        drawing.style.height = `${height}px`
        const ctx = drawing.getContext('2d')
        if (!ctx) return
        ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
        ctx.clearRect(0, 0, width, height)
        ctx.fillStyle = token('--kaori-surface-card', 'Canvas')
        ctx.fillRect(0, 0, width, height)

        const positions = nodes.map((item) => item.position())
        let minX = Math.min(...positions.map((pos) => pos.x))
        let maxX = Math.max(...positions.map((pos) => pos.x))
        let minY = Math.min(...positions.map((pos) => pos.y))
        let maxY = Math.max(...positions.map((pos) => pos.y))
        if (maxX - minX < 1) { minX -= 1; maxX += 1 }
        if (maxY - minY < 1) { minY -= 1; maxY += 1 }
        const padding = 19
        const scale = Math.min((width - 2 * padding) / (maxX - minX), (height - 2 * padding) / (maxY - minY))
        const offsetX = (width - (maxX - minX) * scale) / 2
        const offsetY = (height - (maxY - minY) * scale) / 2
        const point = (position) => ({
            x: offsetX + (position.x - minX) * scale,
            y: offsetY + (position.y - minY) * scale,
        })
        ctx.lineWidth = 1
        ctx.strokeStyle = token('--kaori-outline-strong', 'GrayText')
        edges.forEach((edge) => {
            const from = point(edge.source().position())
            const to = point(edge.target().position())
            ctx.beginPath()
            ctx.moveTo(from.x, from.y)
            ctx.lineTo(to.x, to.y)
            ctx.stroke()
        })
        nodes.forEach((item) => {
            const position = point(item.position())
            const visual = nodeVisual(item.data('type'))
            const selected = item.id() === node.id()
            ctx.beginPath()
            ctx.arc(position.x, position.y, selected ? 5 : 3.25, 0, 2 * Math.PI)
            ctx.fillStyle = visual.fill
            ctx.fill()
            ctx.lineWidth = selected ? 2 : 1
            ctx.strokeStyle = selected ? token('--kaori-brand-primary', 'CanvasText') : visual.border
            ctx.stroke()
        })

        // Same K8s viewport indicator (dashed) for orientation on zoom/pan.
        const extent = cy.extent()
        const topLeft = point({ x: extent.x1, y: extent.y1 })
        const bottomRight = point({ x: extent.x2, y: extent.y2 })
        const x1 = Math.max(1, Math.min(width - 1, Math.min(topLeft.x, bottomRight.x)))
        const y1 = Math.max(1, Math.min(height - 1, Math.min(topLeft.y, bottomRight.y)))
        const x2 = Math.max(x1, Math.min(width - 1, Math.max(topLeft.x, bottomRight.x)))
        const y2 = Math.max(y1, Math.min(height - 1, Math.max(topLeft.y, bottomRight.y)))
        ctx.lineWidth = 1.5
        ctx.strokeStyle = token('--kaori-status-info', 'CanvasText')
        ctx.setLineDash([4, 3])
        ctx.strokeRect(x1, y1, Math.max(1, x2 - x1), Math.max(1, y2 - y1))
        ctx.setLineDash([])

        drawing._kaoriMiniMap = { minX, minY, scale, offsetX, offsetY, width, height, nodes }
        if (!drawing.dataset.kaoriBound) {
            drawing.dataset.kaoriBound = 'true'
            drawing.addEventListener('click', (event) => {
                const state = drawing._kaoriMiniMap
                if (!state || !cy) return
                const rect = drawing.getBoundingClientRect()
                const relativeX = ((event.clientX - rect.left) / Math.max(rect.width, 1)) * state.width
                const relativeY = ((event.clientY - rect.top) / Math.max(rect.height, 1)) * state.height
                const graphX = (relativeX - state.offsetX) / state.scale + state.minX
                const graphY = (relativeY - state.offsetY) / state.scale + state.minY
                let nearest = null
                let distance = Number.POSITIVE_INFINITY
                state.nodes.forEach((item) => {
                    const position = item.position()
                    const nextDistance = Math.hypot(position.x - graphX, position.y - graphY)
                    if (nextDistance < distance) { nearest = item; distance = nextDistance }
                })
                if (nearest?.length) cy.animate({ center: { eles: nearest } }, { duration: 220 })
            })
            drawing.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter' && event.key !== ' ') return
                event.preventDefault()
                cy?.animate({ center: { eles: node } }, { duration: 220 })
            })
        }
    }
    const scheduleDrawerMiniMapUpdate = () => {
        if (drawerMiniMapFrame !== null) window.cancelAnimationFrame(drawerMiniMapFrame)
        drawerMiniMapFrame = window.requestAnimationFrame(drawMiniMap)
    }
    const renderBindingEvidence = (pane, node) => {
        const rows = associatedBindings(node.id())
        if (!rows.length) return
        pane.classList.remove('hidden')
        fill(pane, '[data-runtime-evidence-count]', `${rows.length} ${rows.length === 1 ? 'binding' : 'bindings'}`)
        const list = pane.querySelector('[data-runtime-evidence-rows]')
        for (const item of rows.slice(0, 10)) {
            const card = $('registry-topology-runtime-evidence-row-template')?.content.firstElementChild?.cloneNode(true)
            if (!card || !list) continue
            fill(card, '[data-runtime-workload]', item.workload)
            fill(card, '[data-runtime-pod]', item.pod)
            fill(card, '[data-runtime-cluster]', item.cluster)
            fill(card, '[data-runtime-namespace]', item.namespace)
            const match = String(item.match_type || item.match || '').toLowerCase()
            const matchTone = match.includes('tag') || match.includes('mixed') ? 'warning'
                : match.includes('digest') ? 'info' : 'unknown'
            const matchText = item.confidence
                ? `${safeLabel(item.match)} · ${safeLabel(item.confidence)} confidence`
                : safeLabel(item.match)
            fill(card, '[data-runtime-match-text]', matchText)
            applyStatusSurface(card.querySelector('[data-runtime-match]'),
                card.querySelector('[data-runtime-match-dot]'), matchTone)
            const securityTone = Number(item.critical) > 0 ? 'critical'
                : Number(item.high) > 0 ? 'warning' : 'unknown'
            fill(card, '[data-runtime-security-text]', item.security)
            applyStatusSurface(card.querySelector('[data-runtime-security]'),
                card.querySelector('[data-runtime-security-dot]'), securityTone)
            list.append(card)
        }
        if (rows.length > 10) {
            const more = pane.querySelector('[data-runtime-evidence-more]')
            more?.classList.remove('hidden')
            fill(pane, '[data-runtime-evidence-more]',
                `${rows.length - 10} more visible bindings; refine filters or open Runtime Usage.`)
        }
    }
    const renderRelationshipRows = (target, node) => {
        target.replaceChildren()
        const edges = node.connectedEdges(':visible')
        if (!edges.length) {
            const emptyCard = $('registry-topology-relationships-empty-template')?.content.firstElementChild?.cloneNode(true)
            if (emptyCard) target.append(emptyCard)
            return
        }
        edges.forEach((edge) => {
            const outbound = edge.source().id() === node.id()
            const peer = outbound ? edge.target() : edge.source()
            const row = cloneInspectorTemplate('relationship-row')
            if (!row) return
            row.querySelector('[data-relationship-icon]')?.setAttribute('data-lucide', 'git-branch')
            fill(row, '[data-relationship-direction]', outbound ? 'Outbound' : 'Inbound')
            fill(row, '[data-relationship-label]', relationshipLabels[edge.data('relationship')] || edge.data('relationship'))
            fill(row, '[data-relationship-peer]', peer.data('label'))
            fill(row, '[data-relationship-peer-type]', typeLabels[peer.data('type')] || peer.data('type'))
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
        const posture = evidenceStatus(data)
        fill(pane, '[data-node-evidence]', posture.label)
        applyStatusSurface(pane.querySelector('[data-node-status]'), pane.querySelector('[data-node-status-dot]'), posture.tone)
        fill(pane, '[data-node-description]', data.type === 'artifact'
            ? 'Authoritative Registry artifact identity and reported scan posture.'
            : 'Resource context derived from committed Registry-to-Kubernetes runtime bindings.')
        pane.querySelector('[data-node-description]')?.classList.remove('hidden')
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
                const chip = $('registry-topology-relationship-summary-item-template')?.content.firstElementChild?.cloneNode(true)
                if (!chip) continue
                fill(chip, '[data-summary-label]', `${relationshipLabels[relationship] || relationship} · ${direction === 'out' ? 'Outbound' : 'Inbound'} · ${count}`)
                const color = relationship === 'contains' ? '--kaori-topology-edge-contains'
                    : relationship === 'owns' ? '--kaori-topology-edge-owns' : '--kaori-topology-edge-uses'
                chip.querySelector('[data-summary-swatch]').style.backgroundColor = token(color, 'CanvasText')
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
            else {
                selectedMiniMapNodeId = node.id()
                scheduleDrawerMiniMapUpdate()
            }
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
    const statusSurfaceClasses = {
        healthy: ['bg-status-normal-soft', 'text-status-normal-text', 'bg-status-normal'],
        warning: ['bg-status-warning-soft', 'text-status-warning-text', 'bg-status-warning'],
        critical: ['bg-status-critical-soft', 'text-status-critical-text', 'bg-status-critical'],
        info: ['bg-status-info-soft', 'text-status-info-text', 'bg-status-info'],
        unknown: ['bg-status-unknown-soft', 'text-status-unknown-text', 'bg-status-unknown'],
    }
    const applyStatusSurface = (label, dot, tone) => {
        const normalized = Object.hasOwn(statusSurfaceClasses, tone) ? tone : 'unknown'
        const all = Object.values(statusSurfaceClasses).flat()
        label?.classList.remove(...all)
        dot?.classList.remove(...all)
        const [background, foreground, indicator] = statusSurfaceClasses[normalized]
        label?.classList.add(background, foreground)
        dot?.classList.add(indicator)
    }
    // Scan severity belongs to the Registry artifact. Correlation readiness
    // describes evidence freshness, not Kubernetes health or remediation.
    const evidenceStatus = (data) => {
        if (data.type === 'artifact') {
            const critical = Number(data.critical || 0)
            const high = Number(data.high || 0)
            if (critical > 0) return { label: 'Critical Exposure', tone: 'critical' }
            if (high > 0) return { label: 'High Exposure', tone: 'warning' }
            return { label: data.security || 'Scan Unknown', tone: 'unknown' }
        }
        const readiness = payload.evidence || {}
        return {
            label: readiness.title || 'Evidence Unknown',
            tone: readiness.status === 'ready' ? 'info' :
                ['stale', 'inputs_changed', 'refresh_failed'].includes(readiness.status) ? 'warning' : 'unknown',
        }
    }
    const sortedVisibleResources = () => payload.nodes
        .filter((record) => resourceToggles.find((control) =>
            control.dataset.registryTopologyType === record.data.type
        )?.checked !== false && (!cy || cy.getElementById(record.data.id).visible()))
        .sort((a, b) => (typeLabels[a.data.type] || a.data.type).localeCompare(typeLabels[b.data.type] || b.data.type) ||
            String(a.data.label || '').localeCompare(String(b.data.label || '')))
    const renderList = () => {
        tbody.replaceChildren()
        const nodes = sortedVisibleResources()
        const byId = new Map(payload.nodes.map((node) => [node.data.id, node]))
        const parents = graphParents()
        const total = nodes.length
        for (const item of nodes) {
            const data = item.data
            const scope = resourceScope(item, parents, byId)
            const status = evidenceStatus(data)
            const row = $('registry-topology-resource-list-row-template')?.content.firstElementChild?.cloneNode(true)
            if (!row) continue
            const icon = row.querySelector('[data-list-icon]')
            icon?.setAttribute('data-lucide', typeIcons[data.type] || 'box')
            row.querySelector('[data-list-icon-shell]')?.classList.add(`kaori-topology-domain-${visualDomains[data.type] || 'compute'}`)
            fill(row, '[data-list-name]', data.label)
            fill(row, '[data-list-kind]', data.subtitle || typeLabels[data.type] || data.type)
            fill(row, '[data-list-type]', typeLabels[data.type] || data.type)
            fill(row, '[data-list-cluster]', scope.cluster)
            fill(row, '[data-list-namespace]', scope.namespace)
            fill(row, '[data-list-status-text]', status.label)
            applyStatusSurface(row.querySelector('[data-list-status]'), row.querySelector('[data-list-status-dot]'), status.tone)
            const count = cy
                ? cy.getElementById(data.id).connectedEdges(':visible').length
                : payload.edges.filter((edge) => edge.data.source === data.id || edge.data.target === data.id).length
            fill(row, '[data-list-relationships]', count)
            row.querySelector('[data-list-details]')?.addEventListener('click', () => inspectResource(item))
            tbody.append(row)
        }
        const emptyState = $('registry-topology-list-empty')
        emptyState?.classList.toggle('hidden', Boolean(total))
        window.lucide?.createIcons()
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
    // K8s topology lets Cytoscape apply a bounded external label.
    // Keep the full underlying identity for native ellipsis, hover and inspector.
    const displayLabel = (value) => String(value || 'Not Reported')
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
                    'font-weight': 400,
                    'line-height': 1.2,
                    'min-zoomed-font-size': 8,
                    'text-valign': 'bottom',
                    'text-halign': 'center',
                    'text-justification': 'center',
                    'text-wrap': 'ellipsis',
                    'text-overflow-wrap': 'normal',
                    'text-max-width': 220,
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
                style: { width: 96, height: 52, 'font-size': 11, 'font-weight': 400, 'text-max-width': 240 },
            },
            {
                selector: 'node[type = "cluster"]',
                style: { width: 96, height: 52, 'font-size': 11, 'font-weight': 400, 'text-max-width': 240 },
            },
            { selector: 'node[type = "namespace"]', style: { width: 88, height: 48, 'text-max-width': 230 } },
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
                scheduleDrawerMiniMapUpdate()
                window.setTimeout(() => {
                    fitGraph()
                    scheduleDrawerMiniMapUpdate()
                }, 130)
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
        cy.on('pan zoom resize position layoutstop', scheduleDrawerMiniMapUpdate)
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
        renderEmptyInspector()
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
        $('registry-topology-artifact-focus')?.classList.add('hidden')
        commitFilterChange()
    })
    document.querySelector('#registry-topology-artifact-focus a')?.addEventListener('click', (event) => {
        event.preventDefault()
        window.clearTimeout(searchTimer)
        form.querySelector('input[name="artifact_id"]')?.remove()
        $('registry-topology-artifact-focus')?.classList.add('hidden')
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
    window.addEventListener('resize', scheduleDrawerMiniMapUpdate)
    setView(view)
    renderEmptyInspector()
    syncClearFiltersVisibility()
    reload()
}
