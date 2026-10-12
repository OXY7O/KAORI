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
    const layoutSelect = $('registry-topology-layout')
    const resourceToggles = [...document.querySelectorAll('[data-registry-topology-type]')]
    const relationshipToggles = [...document.querySelectorAll('[data-registry-topology-relationship]')]
    const scopeSummary = $('registry-topology-scope-summary')
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

    const inspect = (node) => {
        const data = node.data()
        inspectorContent.replaceChildren()
        const heading = elements('section', 'rounded-xl border border-outline-subtle bg-surface-elevated p-4')
        const headingRow = elements('div', 'flex items-start gap-3')
        const badge = elements(
            'span',
            `flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border text-sm font-bold kaori-topology-domain-${visualDomains[data.type] || 'compute'}`,
            glyphs[data.type] || 'RS'
        )
        const identity = elements('div', 'min-w-0 flex-1')
        identity.append(elements('p', 'text-xs font-semibold uppercase tracking-wide text-kaori-primary', safeLabel(data.type)))
        identity.append(elements('h4', 'mt-1 break-words text-base font-semibold text-content-primary', safeLabel(data.label)))
        if (data.subtitle) identity.append(elements('p', 'mt-1 text-xs text-content-muted', data.subtitle))
        headingRow.append(badge, identity)
        heading.append(headingRow)
        inspectorContent.append(heading)
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
            const identity = elements('div', 'flex min-w-0 items-center gap-3')
            identity.append(elements('span', 'flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-xs font-bold kaori-topology-domain-configuration', 'AR'))
            const description = elements('div', 'min-w-0')
            description.append(elements('div', 'break-words', item.artifact))
            description.append(elements('div', 'text-xs text-content-muted', item.digest.slice(0, 28)))
            identity.append(description)
            a.append(identity)
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
            // Rotate hierarchy into a left-to-right reading flow. A single
            // artifact should not consume 38rem as a vertical five-node stick.
            transform: (_node, position) => ({ x: position.y, y: position.x }),
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
        cy.nodes().forEach((node) => node.style('display', enabled[node.data('type')] ? 'element' : 'none'))
        cy.edges().forEach((edge) => {
            const included = enabled[edge.source().data('type')] &&
                enabled[edge.target().data('type')] &&
                relationships[edge.data('relationship')]
            edge.style('display', included ? 'element' : 'none')
        })
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
                window.setTimeout(fitGraph, 130)
            })
        })
        layout.run()
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
            inspectorContent.replaceChildren()
            inspectorContent.append(elements('h4', 'text-lg font-semibold text-content-primary', 'Relationship Evidence'))
            const details = elements('div', 'rounded-lg border border-outline-default p-4')
            appendField(details, 'Relationship', edge.data('relationship'))
            appendField(details, 'Match Confidence', edge.data('confidence'))
            appendField(details, 'From', edge.source().data('label'))
            appendField(details, 'To', edge.target().data('label'))
            inspectorContent.append(details)
            inspectorContent.append(elements('p', 'text-xs text-content-muted', 'Containment and ownership are presentation context from committed Registry-to-Pod bindings. Digest matches are stronger than tag-only evidence.'))
            openInspector()
        })
        updateEdgeLabelClasses()
        graphHasLayout = false
        setView(view)
    }

    const reload = async () => {
        if (controller) controller.abort()
        controller = new AbortController()
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
                signal: controller.signal,
                credentials: 'same-origin',
            })
            if (!response.ok) throw new Error(`Graph request failed (HTTP ${response.status})`)
            payload = await response.json()
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
    reload()
}
