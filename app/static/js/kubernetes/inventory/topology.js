const config = window.KAORI_TOPOLOGY
const runtimeStatusPanel = document.getElementById('topology-runtime-status')
const startupErrorPanel = document.getElementById('topology-error')

if (!config) {
    throw new Error('KAORI topology configuration is unavailable.')
}

let topologyRenderer
try {
    const cytoscapeModule = await import(config.renderer_url)
    topologyRenderer = cytoscapeModule.c
    window.KAORI_TOPOLOGY_LIBRARY_VERSION = topologyRenderer?.version || 'unknown'
} catch (error) {
    console.error('KAORI topology renderer could not start.', error)
    if (runtimeStatusPanel) runtimeStatusPanel.classList.add('hidden')
    if (startupErrorPanel) {
        startupErrorPanel.textContent = `Topology renderer could not start: ${error?.message || 'unknown JavaScript error'}`
        startupErrorPanel.classList.remove('hidden')
    }
    throw error
}

const startTopologyWorkspace = () => {
    const $ = (id) => document.getElementById(id)
    const canvas = $('topology-canvas')
    const canvasShell = $('topology-canvas-shell')
    const boundaryLayer = $('topology-namespace-boundaries')
    const clusterSelect = $('topology-cluster')
    const namespaceSelect = $('topology-namespace')
    const scopeSelect = $('topology-scope')
    const depthSelect = $('topology-depth')
    const searchInput = $('topology-search')
    const searchResults = $('topology-search-results')
    const loading = $('topology-loading')
    const controlsPanel = $('topology-controls-panel')
    const detailsPanel = $('topology-details-panel')
    const paneBackdrop = $('topology-pane-backdrop')
    const graphPanel = $('topology-view-panel-graph')
    const listPanel = $('topology-view-panel-list')
    const resourceListBody = $('topology-resource-list-body')
    const resourceListEmpty = $('topology-resource-list-empty')
    const viewTabs = Array.from(document.querySelectorAll('[data-kaori-segmented-group="topology-view"]'))
    const errorPanel = $('topology-error')
    const runtimeStatus = $('topology-runtime-status')
    const emptyState = $('topology-empty-state')
    const limitWarning = $('topology-limit-warning')
    const limitMessage = $('topology-limit-message')
    const detailContent = $('topology-detail-content')
    const nodeLabelToggle = $('topology-node-label-toggle')
    const edgeLabelToggle = $('topology-edge-label-toggle')
    const layoutModeSelect = $('topology-layout-mode')
    const groupNamespaceToggle = $('topology-group-namespace-toggle')
    const relationshipToggles = Array.from(document.querySelectorAll('[data-topology-relationship-toggle]'))
    const resourceToggles = Array.from(document.querySelectorAll('[data-topology-resource-toggle]'))
    const searchSummary = $('topology-search-summary')
    const filterSummary = $('topology-filter-summary')
    const clearFiltersButton = $('topology-clear-filters-button')

    if (!canvas || !clusterSelect || !namespaceSelect || !scopeSelect || !depthSelect) return

    const STATE_KEY = 'kaori.topology.workspace.v5'
    const resourceTypes = [
        'cluster',
        'namespace',
        'node',
        'workload',
        'pod',
        'service',
        'ingress',
        'configmap',
        'secret',
        'pvc',
        'pv',
    ]
    const relationshipTypes = ['contains', 'owns', 'scheduled_on', 'selects', 'routes_to', 'uses', 'mounts', 'binds']

    let cy = null
    let currentPayload = config.initial_graph || { nodes: [], edges: [], summary: {}, type_counts: {} }
    let fetchController = null
    let searchTimer = null
    let selectedNodeId = null
    let activeDrawerTab = 'details'
    let activeView = new URL(window.location.href).searchParams.get('view') === 'list' ? 'list' : 'graph'
    let searchResultNodes = []
    let activeSearchIndex = -1
    let pathHighlightActive = false
    let boundaryFrame = null
    let drawerMiniMapFrame = null
    let collapsedNodeIds = new Set()
    let collapsedHiddenIds = new Set()
    let childrenByNode = new Map()

    const cssToken = (name, fallback = '') =>
        window.getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback

    const domainForType = (type) =>
        ({
            cluster: 'scope',
            namespace: 'scope',
            node: 'compute',
            workload: 'compute',
            pod: 'compute',
            service: 'networking',
            ingress: 'networking',
            configmap: 'configuration',
            secret: 'configuration',
            pvc: 'storage',
            pv: 'storage',
        })[type] || 'compute'

    const getTypeVisual = (type) => {
        const domain = domainForType(type)
        return {
            fill: cssToken(`--kaori-topology-domain-${domain}-fill`, 'CanvasText'),
            border: cssToken(`--kaori-topology-domain-${domain}-border`, 'CanvasText'),
            text: cssToken(`--kaori-topology-domain-${domain}-text`, 'Canvas'),
            shape: 'round-rectangle',
        }
    }

    const typeUi = {
        cluster: { icon: 'server', domain: 'scope' },
        namespace: { icon: 'layers-3', domain: 'scope' },
        node: { icon: 'server', domain: 'compute' },
        workload: { icon: 'boxes', domain: 'compute' },
        pod: { icon: 'circle-dot', domain: 'compute' },
        service: { icon: 'network', domain: 'networking' },
        ingress: { icon: 'route', domain: 'networking' },
        configmap: { icon: 'file-cog', domain: 'configuration' },
        secret: { icon: 'key-round', domain: 'configuration' },
        pvc: { icon: 'database', domain: 'storage' },
        pv: { icon: 'hard-drive', domain: 'storage' },
    }

    const edgeTokenNames = {
        owns: '--kaori-topology-edge-owns',
        scheduled_on: '--kaori-topology-edge-scheduled',
        selects: '--kaori-topology-edge-selects',
        routes_to: '--kaori-topology-edge-routes',
        uses: '--kaori-topology-edge-uses',
        mounts: '--kaori-topology-edge-mounts',
        binds: '--kaori-topology-edge-binds',
        contains: '--kaori-topology-edge-contains',
    }
    const edgeColor = (relationship) =>
        cssToken(edgeTokenNames[relationship] || '--kaori-topology-edge-contains', 'CanvasText')

    const relationshipUi = {
        owns: { icon: 'boxes' },
        scheduled_on: { icon: 'server' },
        selects: { icon: 'network' },
        routes_to: { icon: 'route' },
        uses: { icon: 'link-2' },
        mounts: { icon: 'database' },
        binds: { icon: 'hard-drive' },
        contains: { icon: 'folder-tree' },
    }

    const statusSurfaceClasses = {
        healthy: ['bg-status-normal-soft', 'text-status-normal-text', 'bg-status-normal'],
        warning: ['bg-status-warning-soft', 'text-status-warning-text', 'bg-status-warning'],
        critical: ['bg-status-critical-soft', 'text-status-critical-text', 'bg-status-critical'],
        info: ['bg-status-info-soft', 'text-status-info-text', 'bg-status-info'],
        unknown: ['bg-status-unknown-soft', 'text-status-unknown-text', 'bg-status-unknown'],
    }

    const statusDotColor = (tone) =>
        ({
            healthy: cssToken('--kaori-status-normal', 'CanvasText'),
            warning: cssToken('--kaori-status-warning', 'CanvasText'),
            critical: cssToken('--kaori-status-critical', 'CanvasText'),
            info: cssToken('--kaori-status-info', 'CanvasText'),
            unknown: cssToken('--kaori-status-unknown', 'GrayText'),
        })[tone] || cssToken('--kaori-status-unknown', 'GrayText')

    const humanizeType = (value) =>
        ({
            cluster: 'Cluster',
            namespace: 'Namespace',
            node: 'Node',
            workload: 'Workload',
            pod: 'Pod',
            service: 'Service',
            ingress: 'Ingress',
            configmap: 'ConfigMap',
            secret: 'Secret',
            pvc: 'PVC',
            pv: 'PV',
        })[value] || value

    const pluralizeType = (value, count) => {
        if (Number(count) === 1) return humanizeType(value)
        return (
            {
                cluster: 'Clusters',
                namespace: 'Namespaces',
                node: 'Nodes',
                workload: 'Workloads',
                pod: 'Pods',
                service: 'Services',
                ingress: 'Ingresses',
                configmap: 'ConfigMaps',
                secret: 'Secrets',
                pvc: 'PVCs',
                pv: 'PVs',
            }[value] || `${humanizeType(value)} Resources`
        )
    }

    const titleCaseText = (value) =>
        String(value ?? '')
            .replaceAll('_', ' ')
            .replaceAll('-', ' ')
            .replace(/\b[a-z]/g, (character) => character.toUpperCase())

    const nodeBadgeCache = new Map()
    const nodeTypeGlyph = (type) =>
        ({
            cluster: 'CL',
            namespace: 'NS',
            node: 'ND',
            workload: 'WL',
            pod: 'PD',
            service: 'SV',
            ingress: 'IN',
            configmap: 'CM',
            secret: 'SC',
            pvc: 'PC',
            pv: 'PV',
        })[type] || 'RS'

    const nodeBadgeSvg = (type, tone) => {
        const visual = getTypeVisual(type)
        const normalizedTone = ['healthy', 'warning', 'critical', 'info'].includes(tone) ? tone : 'unknown'
        const statusColor = statusDotColor(normalizedTone)
        const statusOutline = cssToken('--kaori-surface-card', 'Canvas')
        const glyph = nodeTypeGlyph(type)
        const cacheKey = `${type}:${normalizedTone}:${visual.text}:${statusColor}:${statusOutline}`
        if (nodeBadgeCache.has(cacheKey)) return nodeBadgeCache.get(cacheKey)
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="52" viewBox="0 0 96 52"><text x="48" y="32" text-anchor="middle" font-family="Inter, sans-serif" font-size="16" font-weight="700" fill="${visual.text}">${glyph}</text><circle cx="84" cy="10" r="5" fill="${statusColor}" stroke="${statusOutline}" stroke-width="2"/></svg>`
        const uri = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
        nodeBadgeCache.set(cacheKey, uri)
        return uri
    }

    const formatDateTime = (value) => {
        if (!value) return 'Not Reported'
        const parsed = new Date(value)
        if (Number.isNaN(parsed.getTime())) return value
        return new Intl.DateTimeFormat(undefined, {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZoneName: 'short',
        }).format(parsed)
    }

    const getTypeUi = (type) => typeUi[type] || typeUi.node
    const getRelationshipUi = (relationship) => relationshipUi[relationship] || { icon: 'git-commit-horizontal' }

    const defaultWorkspaceState = () => ({
        nodeLabels: true,
        edgeLabels: false,
        groupByNamespace: false,
        resources: Object.fromEntries(resourceTypes.map((type) => [type, true])),
        relationships: Object.fromEntries(relationshipTypes.map((type) => [type, true])),
    })

    const loadWorkspaceState = () => {
        const defaults = defaultWorkspaceState()
        try {
            const saved = JSON.parse(window.localStorage.getItem(STATE_KEY) || '{}')
            return {
                ...defaults,
                ...saved,
                resources: { ...defaults.resources, ...(saved.resources || {}) },
                relationships: { ...defaults.relationships, ...(saved.relationships || {}) },
            }
        } catch (error) {
            console.warn('KAORI topology state could not be restored.', error)
            return defaults
        }
    }

    let workspaceState = loadWorkspaceState()

    const saveWorkspaceState = () => {
        try {
            window.localStorage.setItem(STATE_KEY, JSON.stringify(workspaceState))
        } catch (error) {
            console.warn('KAORI topology state could not be saved.', error)
        }
    }

    const closePanes = () => {
        paneBackdrop?.classList.add('hidden')
        document.body.classList.remove('overflow-hidden')
        controlsPanel?.classList.add('hidden')
        detailsPanel?.classList.add('hidden')
    }

    const openPane = (panel) => {
        if (!panel) return
        controlsPanel?.classList.add('hidden')
        detailsPanel?.classList.add('hidden')
        panel.classList.remove('hidden')
        paneBackdrop?.classList.remove('hidden')
        document.body.classList.add('overflow-hidden')
        panel.querySelector('button, [href], input, select')?.focus({ preventScroll: true })
    }

    const setActiveView = (view, { updateUrl = true } = {}) => {
        const graphTab = viewTabs.find((button) => button.dataset.kaoriSegmentedTab === 'graph')
        activeView = view === 'list' || graphTab?.disabled ? 'list' : 'graph'
        if (graphPanel) graphPanel.hidden = activeView !== 'graph'
        if (listPanel) listPanel.hidden = activeView !== 'list'
        viewTabs.forEach((button) => {
            const active = button.dataset.kaoriSegmentedTab === activeView
            button.setAttribute('aria-selected', active ? 'true' : 'false')
            button.tabIndex = active ? 0 : -1
            button.classList.toggle('bg-surface-card', active)
            button.classList.toggle('text-kaori-primary', active)
            button.classList.toggle('shadow-sm', active)
            button.classList.toggle('text-content-muted', !active)
        })
        if (activeView === 'list') renderResourceList()
        else if (cy)
            window.requestAnimationFrame(() => {
                cy.resize()
                fitGraphToCanvas()
            })
        if (updateUrl) updateUrl()
    }

    const bindSegmentedKeyboard = (buttons, activate) => {
        buttons.forEach((button) =>
            button.addEventListener('keydown', (event) => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
                const enabledButtons = buttons.filter((item) => !item.disabled)
                const index = enabledButtons.indexOf(button)
                if (index < 0 || !enabledButtons.length) return
                event.preventDefault()
                let nextIndex = index
                if (event.key === 'ArrowRight') nextIndex = (index + 1) % enabledButtons.length
                if (event.key === 'ArrowLeft') nextIndex = (index - 1 + enabledButtons.length) % enabledButtons.length
                if (event.key === 'Home') nextIndex = 0
                if (event.key === 'End') nextIndex = enabledButtons.length - 1
                enabledButtons[nextIndex]?.focus()
                activate(enabledButtons[nextIndex])
            })
        )
    }

    const relationshipCountsByNode = () => {
        const counts = new Map()
        ;(currentPayload.edges || []).forEach((edge) => {
            const data = edge?.data || {}
            if (workspaceState.relationships[data.relationship] === false) return
            if (data.source) counts.set(data.source, (counts.get(data.source) || 0) + 1)
            if (data.target) counts.set(data.target, (counts.get(data.target) || 0) + 1)
        })
        return counts
    }

    const visibleNodeRecords = () => {
        if (cy) {
            return cy.nodes(':visible').map((node) => ({
                id: () => node.id(),
                data: (key) => (key ? node.data(key) : node.data()),
                relationshipCount: () => node.connectedEdges(':visible').length,
                graphNode: node,
            }))
        }
        const relationshipCounts = relationshipCountsByNode()
        return (currentPayload.nodes || [])
            .filter((item) => {
                const type = item?.data?.type
                return item?.data?.id && workspaceState.resources[type] !== false
            })
            .map((item) => {
                const data = item.data || {}
                return {
                    id: () => data.id,
                    data: (key) => (key ? data[key] : data),
                    relationshipCount: () => relationshipCounts.get(data.id) || 0,
                    graphNode: null,
                }
            })
    }

    const sortedVisibleNodeRecords = () =>
        visibleNodeRecords().sort((a, b) => {
            const typeCompare = humanizeType(a.data('type')).localeCompare(humanizeType(b.data('type')))
            return typeCompare || String(a.data('label') || '').localeCompare(String(b.data('label') || ''))
        })

    const renderResourceList = () => {
        if (!resourceListBody) return
        resourceListBody.replaceChildren()
        const nodes = sortedVisibleNodeRecords()
        resourceListEmpty?.classList.toggle('hidden', nodes.length > 0)
        if (!nodes.length) return
        nodes.forEach((node) => {
            const data = node.data()
            const ui = getTypeUi(data.type)
            const row = cloneTemplate('topology-resource-list-row-template')
            if (!row) return
            row.querySelector('[data-list-icon]')?.setAttribute('data-lucide', ui.icon)
            row.querySelector('[data-list-icon-shell]')?.classList.add(`kaori-topology-domain-${ui.domain}`)
            text(row, '[data-list-name]', data.label || node.id())
            text(row, '[data-list-kind]', data.kind || humanizeType(data.type))
            text(row, '[data-list-type]', humanizeType(data.type))
            text(row, '[data-list-cluster]', data.cluster_name || 'Not Reported')
            text(row, '[data-list-namespace]', data.namespace || 'Cluster Scoped')
            text(row, '[data-list-status-text]', titleCaseText(data.status || 'Unknown'))
            applyStatusSurface(
                row.querySelector('[data-list-status]'),
                row.querySelector('[data-list-status-dot]'),
                data.status_tone
            )
            text(row, '[data-list-relationships]', node.relationshipCount())
            row.querySelector('[data-list-details]')?.addEventListener('click', () => selectNodeById(node.id()))
            resourceListBody.appendChild(row)
        })
        window.lucide?.createIcons()
    }

    const graphStyle = () => {
        const labelBackground = cssToken('--kaori-surface-card', 'Canvas')
        const labelText = cssToken('--kaori-content-primary', 'CanvasText')
        const brandPrimary = cssToken('--kaori-brand-primary', 'CanvasText')
        const brandAccent = cssToken('--kaori-brand-accent', 'CanvasText')
        return [
            {
                selector: 'node',
                style: {
                    'background-color': (node) => getTypeVisual(node.data('type')).fill,
                    'border-color': (node) => getTypeVisual(node.data('type')).border,
                    'border-width': 2,
                    color: labelText,
                    'font-family': 'Inter, sans-serif',
                    'font-size': 10,
                    'font-weight': 600,
                    height: 44,
                    label: workspaceState.nodeLabels ? 'data(display_label)' : '',
                    'line-height': 1.2,
                    'min-zoomed-font-size': 8,
                    'overlay-opacity': 0,
                    padding: 0,
                    shape: 'round-rectangle',
                    'shadow-blur': 10,
                    'shadow-color': cssToken('--kaori-content-primary', 'CanvasText'),
                    'shadow-offset-x': 0,
                    'shadow-offset-y': 3,
                    'shadow-opacity': 0.1,
                    'text-background-color': labelBackground,
                    'text-background-opacity': 0.94,
                    'text-background-padding': 3,
                    'text-background-shape': 'roundrectangle',
                    'text-border-color': cssToken('--kaori-outline-subtle', 'GrayText'),
                    'text-border-opacity': 0.8,
                    'text-border-width': 1,
                    'text-halign': 'center',
                    'text-justification': 'center',
                    'text-margin-y': 11,
                    'text-max-width': 220,
                    'text-overflow-wrap': 'normal',
                    'text-valign': 'bottom',
                    'text-wrap': 'ellipsis',
                    width: 76,
                    'background-image': (node) => nodeBadgeSvg(node.data('type'), node.data('status_tone')),
                    'background-width': '100%',
                    'background-height': '100%',
                    'background-position-x': '50%',
                    'background-position-y': '50%',
                    'background-repeat': 'no-repeat',
                    'background-fit': 'none',
                    'background-image-containment': 'inside',
                },
            },
            {
                selector: 'node[type = "cluster"]',
                style: { 'font-size': 11, 'font-weight': 700, height: 52, 'text-max-width': 240, width: 96 },
            },
            { selector: 'node[type = "namespace"]', style: { height: 48, 'text-max-width': 230, width: 88 } },
            {
                selector: 'edge',
                style: {
                    'curve-style': 'bezier',
                    'font-family': 'Inter, sans-serif',
                    'font-size': 9,
                    'font-weight': 600,
                    label: '',
                    'line-color': (edge) => edgeColor(edge.data('relationship')),
                    'line-opacity': 0.68,
                    'min-zoomed-font-size': 8,
                    'overlay-opacity': 0,
                    'target-arrow-color': (edge) => edgeColor(edge.data('relationship')),
                    'target-arrow-shape': 'triangle',
                    'arrow-scale': 0.78,
                    color: labelText,
                    'text-background-color': labelBackground,
                    'text-background-opacity': 0.96,
                    'text-background-padding': 4,
                    'text-rotation': 'autorotate',
                    width: 1.5,
                },
            },
            {
                selector: 'edge[relationship = "contains"]',
                style: {
                    'curve-style': 'taxi',
                    'line-style': 'dashed',
                    'line-opacity': 0.28,
                    'target-arrow-shape': 'none',
                    'taxi-direction': 'downward',
                    'taxi-turn': 24,
                    width: 1,
                },
            },
            { selector: 'edge.edge-label-visible', style: { label: 'data(label)' } },
            { selector: '.dimmed', style: { opacity: 0.1, 'text-opacity': 0.06 } },
            { selector: '.focused', style: { opacity: 1, 'text-opacity': 1, 'z-index': 999 } },
            {
                selector: '.path-active',
                style: {
                    opacity: 1,
                    'text-opacity': 1,
                    'z-index': 1100,
                    'line-opacity': 1,
                    width: 3,
                    label: 'data(label)',
                },
            },
            { selector: 'node.path-active', style: { 'border-width': 3, 'shadow-opacity': 0.22 } },
            {
                selector: '.search-match',
                style: { 'border-color': brandAccent, 'border-width': 3, opacity: 1, 'z-index': 1150 },
            },
            {
                selector: ':selected',
                style: {
                    'border-color': brandPrimary,
                    'border-width': 3,
                    'line-color': brandPrimary,
                    'target-arrow-color': brandPrimary,
                    'z-index': 1200,
                },
            },
        ]
    }

    const getLayoutMode = () => (layoutModeSelect?.value === 'dependency' ? 'dependency' : 'hierarchy')

    const layoutOptions = () => {
        if (getLayoutMode() === 'dependency') {
            return {
                name: 'cose',
                animate: 'end',
                animationDuration: 420,
                animationEasing: 'ease-out-cubic',
                fit: true,
                nodeDimensionsIncludeLabels: true,
                padding: 80,
                idealEdgeLength: 210,
                edgeElasticity: 100,
                nodeRepulsion: 620000,
                gravity: 0.3,
                numIter: 1600,
                componentSpacing: 165,
                nestingFactor: 0.8,
                initialTemp: 200,
                coolingFactor: 0.96,
                minTemp: 1,
                randomize: true,
            }
        }
        return {
            name: 'breadthfirst',
            animate: false,
            circle: false,
            directed: true,
            fit: true,
            grid: true,
            maximal: false,
            nodeDimensionsIncludeLabels: true,
            padding: 64,
            spacingFactor: 1.88,
        }
    }

    const prepareElements = (payload) => {
        const rawNodes = Array.isArray(payload.nodes) ? payload.nodes : []
        const rawEdges = Array.isArray(payload.edges) ? payload.edges : []
        const nodeIds = new Set(rawNodes.map((node) => node?.data?.id).filter(Boolean))
        const containmentEdges = []
        const nodes = rawNodes.map((node) => {
            const data = { ...(node.data || {}) }
            data.base_label = String(data.label || data.id || '').trim()
            data.type_label = humanizeType(data.type)
            data.display_label = data.base_label
            const parent = data.parent
            delete data.parent
            if (parent && nodeIds.has(parent) && data.id) {
                containmentEdges.push({
                    data: {
                        id: `contains:${parent}:${data.id}`,
                        source: parent,
                        target: data.id,
                        relationship: 'contains',
                        label: 'contains',
                        source_label: parent,
                        target_label: data.label || data.id,
                        description: 'The parent inventory scope contains this Kubernetes resource.',
                    },
                })
            }
            return { ...node, data }
        })
        const existing = new Set(rawEdges.map((edge) => edge?.data?.id).filter(Boolean))
        const edges = [...rawEdges, ...containmentEdges.filter((edge) => !existing.has(edge.data.id))]
        return { nodes, edges, elements: [...nodes, ...edges] }
    }

    const ensureCanvasDimensions = () => {
        if (!canvas || !canvasShell) return { width: 0, height: 0 }
        canvas.style.position = 'absolute'
        canvas.style.inset = '0'
        canvas.style.width = '100%'
        canvas.style.height = '100%'
        return canvas.getBoundingClientRect()
    }

    const visibleGraphElements = () => {
        if (!cy) return null
        const visibleNodes = cy.nodes().filter((node) => node.style('display') !== 'none')
        const visibleEdges = cy.edges().filter((edge) => edge.style('display') !== 'none')
        return visibleNodes.union(visibleEdges)
    }

    const fitGraphToCanvas = () => {
        if (!cy) return
        const visible = visibleGraphElements()
        if (!visible || !visible.nodes().length) return
        ensureCanvasDimensions()
        cy.resize()
        const rect = canvas.getBoundingClientRect()
        const shortest = Math.min(rect.width || 0, rect.height || 0)
        const padding = Math.max(48, Math.min(88, Math.round(shortest * 0.08)))
        cy.fit(visible, padding)
        cy.center(visible)
    }

    const setRuntimeStatus = (message = '') => {
        if (!runtimeStatus) return
        if (!message) {
            runtimeStatus.classList.add('hidden')
            runtimeStatus.replaceChildren()
            return
        }
        runtimeStatus.classList.remove('hidden')
        const row = document.createElement('span')
        row.className = 'inline-flex items-center gap-2'
        const dot = document.createElement('span')
        dot.className = 'h-2 w-2 rounded-full bg-status-pending'
        const copy = document.createElement('span')
        copy.textContent = message
        row.append(dot, copy)
        runtimeStatus.replaceChildren(row)
    }

    const showError = (message = '') => {
        if (!errorPanel) return
        if (!message) {
            errorPanel.classList.add('hidden')
            errorPanel.textContent = ''
            return
        }
        errorPanel.textContent = message
        errorPanel.classList.remove('hidden')
    }

    const updateNamespaceOptions = (selectedValue = '') => {
        const clusterId = clusterSelect.value
        const namespaces = config.namespace_map?.[clusterId] || []
        const allOption = document.createElement('option')
        allOption.value = ''
        allOption.textContent = 'All Namespaces'
        namespaceSelect.replaceChildren(allOption)
        namespaces.forEach((namespace) => {
            const option = document.createElement('option')
            option.value = namespace
            option.textContent = namespace
            option.selected = namespace === selectedValue
            namespaceSelect.appendChild(option)
        })
        namespaceSelect.disabled = !clusterId
        if (!clusterId) namespaceSelect.value = ''
    }

    const syncLayoutFromUrl = () => {
        if (!layoutModeSelect) return
        const value = new URL(window.location.href).searchParams.get('layout')
        layoutModeSelect.value = value === 'dependency' ? 'dependency' : 'hierarchy'
    }

    const hasActiveFilters = () =>
        Boolean(
            clusterSelect.value ||
                (!namespaceSelect.disabled && namespaceSelect.value) ||
                scopeSelect.value !== 'all' ||
                depthSelect.value !== '1' ||
                searchInput.value.trim()
        )

    const syncClearFiltersVisibility = () => {
        if (clearFiltersButton) clearFiltersButton.hidden = !hasActiveFilters()
    }

    const updateUrl = () => {
        const url = new URL(window.location.href)
        const values = {
            cluster_id: clusterSelect.value,
            namespace: namespaceSelect.disabled ? '' : namespaceSelect.value,
            scope: scopeSelect.value,
            depth: depthSelect.value,
            layout: getLayoutMode(),
            view: activeView,
        }
        Object.entries(values).forEach(([key, value]) => {
            const isDefault =
                (key === 'scope' && value === 'all') ||
                (key === 'depth' && value === '1') ||
                (key === 'layout' && value === 'hierarchy') ||
                (key === 'view' && value === 'graph')
            if (value && !isDefault) url.searchParams.set(key, value)
            else url.searchParams.delete(key)
        })
        window.history.replaceState({}, '', url)
        syncClearFiltersVisibility()
    }

    const applyStateToControls = () => {
        if (nodeLabelToggle) nodeLabelToggle.checked = workspaceState.nodeLabels
        if (edgeLabelToggle) edgeLabelToggle.checked = workspaceState.edgeLabels
        if (groupNamespaceToggle) groupNamespaceToggle.checked = workspaceState.groupByNamespace
        resourceToggles.forEach((toggle) => {
            toggle.checked = workspaceState.resources[toggle.dataset.topologyResourceToggle] !== false
        })
        relationshipToggles.forEach((toggle) => {
            toggle.checked = workspaceState.relationships[toggle.dataset.topologyRelationshipToggle] !== false
        })
    }

    const updateSummary = (payload) => {
        const summary = payload.summary || {}
        const setText = (id, value) => {
            const element = $(id)
            if (element) element.textContent = value
        }
        setText('topology-hero-clusters', summary.clusters ?? 0)
        setText('topology-hero-namespaces', summary.namespaces ?? 0)
        setText('topology-hero-resources', summary.resources ?? 0)
        setText('topology-hero-relationships', summary.relationships ?? 0)
        setText('topology-hero-coverage', summary.omitted_nodes ?? 0)
        $('topology-hero-coverage-complete')?.classList.toggle('hidden', Boolean(summary.truncated))
        $('topology-hero-coverage-limited')?.classList.toggle('hidden', !summary.truncated)
        if (filterSummary)
            filterSummary.textContent = `${summary.scope_label || 'All Resources'} · ${summary.depth_label || '1 Level'}`
        document.querySelectorAll('[data-topology-count-type]').forEach((element) => {
            element.textContent = payload.type_counts?.[element.dataset.topologyCountType] ?? 0
        })
        if (summary.truncated) {
            limitWarning?.classList.remove('hidden')
            const omittedBreakdown = Object.entries(summary.omitted_by_type || {})
                .filter(([, count]) => Number(count) > 0)
                .sort((a, b) => Number(b[1]) - Number(a[1]))
                .slice(0, 3)
                .map(([type, count]) => `${count} ${pluralizeType(type, count)}`)
                .join(', ')
            if (limitMessage) {
                limitMessage.textContent = `${summary.omitted_nodes || 0} resources were omitted${omittedBreakdown ? ` (${omittedBreakdown})` : ''}. Narrow the cluster or namespace scope to display them.`
            }
        } else {
            limitWarning?.classList.add('hidden')
        }
    }

    const buildHierarchyIndex = () => {
        childrenByNode = new Map()
        if (!cy) return
        cy.edges().forEach((edge) => {
            if (!['contains', 'owns'].includes(edge.data('relationship'))) return
            const source = edge.source().id()
            if (!childrenByNode.has(source)) childrenByNode.set(source, new Set())
            childrenByNode.get(source).add(edge.target().id())
        })
    }

    const descendantsOf = (nodeId) => {
        const result = new Set()
        const queue = [...(childrenByNode.get(nodeId) || [])]
        while (queue.length) {
            const current = queue.shift()
            if (result.has(current)) continue
            result.add(current)
            queue.push(...(childrenByNode.get(current) || []))
        }
        return result
    }

    const recomputeCollapsedHidden = () => {
        collapsedHiddenIds = new Set()
        collapsedNodeIds.forEach((nodeId) => descendantsOf(nodeId).forEach((id) => collapsedHiddenIds.add(id)))
        if (!cy) return
        cy.nodes().forEach((node) => {
            const base = node.data('base_label') || node.data('label') || node.id()
            if (collapsedNodeIds.has(node.id())) {
                const count = descendantsOf(node.id()).size
                node.data('display_label', `${base} (+${count})`)
            } else {
                node.data('display_label', base)
            }
        })
    }

    const enabledResourceTypes = () =>
        new Set(
            resourceToggles.filter((toggle) => toggle.checked).map((toggle) => toggle.dataset.topologyResourceToggle)
        )
    const enabledRelationshipTypes = () =>
        new Set(
            relationshipToggles
                .filter((toggle) => toggle.checked)
                .map((toggle) => toggle.dataset.topologyRelationshipToggle)
        )

    const updateEdgeLabelClasses = () => {
        if (!cy) return
        cy.edges().removeClass('edge-label-visible')
        if (workspaceState.edgeLabels) cy.edges(':visible').addClass('edge-label-visible')
        cy.edges('.path-active').addClass('edge-label-visible')
        if (selectedNodeId && !pathHighlightActive) {
            const node = cy.getElementById(selectedNodeId)
            if (node?.length) node.connectedEdges(':visible').addClass('edge-label-visible')
        }
    }

    const applyVisibility = ({ relayout = false } = {}) => {
        if (!cy) {
            renderResourceList()
            return
        }
        recomputeCollapsedHidden()
        const resources = enabledResourceTypes()
        const relationships = enabledRelationshipTypes()
        cy.nodes().forEach((node) => {
            const visible = resources.has(node.data('type')) && !collapsedHiddenIds.has(node.id())
            node.style('display', visible ? 'element' : 'none')
        })
        cy.edges().forEach((edge) => {
            const endpointsVisible =
                edge.source().style('display') !== 'none' && edge.target().style('display') !== 'none'
            const visible = relationships.has(edge.data('relationship')) && endpointsVisible
            edge.style('display', visible ? 'element' : 'none')
        })

        let visibleNodes = cy.nodes().filter((node) => node.style('display') !== 'none')
        if (!visibleNodes.length && cy.nodes().length) {
            resourceToggles.forEach((toggle) => {
                toggle.checked = true
                workspaceState.resources[toggle.dataset.topologyResourceToggle] = true
            })
            saveWorkspaceState()
            cy.nodes().style('display', 'element')
            cy.edges().forEach((edge) => {
                const enabled = relationships.has(edge.data('relationship'))
                edge.style('display', enabled ? 'element' : 'none')
            })
            visibleNodes = cy.nodes()
        }

        updateEdgeLabelClasses()
        scheduleBoundaryUpdate()
        if (selectedNodeId) {
            const selected = cy.getElementById(selectedNodeId)
            if (selected?.length && selected.style('display') !== 'none') renderNodeDetails(selected, activeDrawerTab)
            else clearSelection()
        }
        renderResourceList()
        if (relayout) applyCurrentLayout()
    }

    const clearPathHighlight = ({ preserveSelection = true } = {}) => {
        if (!cy) return
        pathHighlightActive = false
        cy.elements().removeClass('path-active dimmed focused')
        if (preserveSelection && selectedNodeId) {
            const node = cy.getElementById(selectedNodeId)
            if (node?.length && node.visible()) focusNeighborhood(node)
        }
        updateEdgeLabelClasses()
    }

    const anchorCandidatesFor = (node) => {
        if (!cy) return []
        const data = node.data()
        const sameCluster = cy.nodes(':visible').filter((candidate) => candidate.data('cluster_id') === data.cluster_id)
        const anchors = []
        const add = (collection) =>
            collection.forEach((item) => {
                if (item.id() !== node.id() && !anchors.some((existing) => existing.id() === item.id()))
                    anchors.push(item)
            })
        add(sameCluster.filter('[type = "cluster"]'))
        if (data.namespace)
            add(
                sameCluster.filter(
                    (candidate) =>
                        candidate.data('type') === 'namespace' && candidate.data('namespace') === data.namespace
                )
            )
        add(
            node
                .connectedEdges(':visible')
                .connectedNodes(':visible')
                .filter('[type = "workload"], [type = "node"], [type = "service"], [type = "ingress"]')
        )
        return anchors.slice(0, 8)
    }

    const highlightPaths = (node) => {
        if (!cy || !node?.length) return
        clearPathHighlight({ preserveSelection: false })
        const visible = cy.elements(':visible')
        let path = node
        anchorCandidatesFor(node).forEach((anchor) => {
            const result = visible.aStar({ root: node, goal: anchor, directed: false })
            if (result.found) path = path.union(result.path)
        })
        path = path.union(node.closedNeighborhood(':visible'))
        cy.elements(':visible').addClass('dimmed')
        path.removeClass('dimmed').addClass('path-active focused')
        node.select()
        selectedNodeId = node.id()
        pathHighlightActive = true
        updateEdgeLabelClasses()
        renderNodeDetails(node, activeDrawerTab)
    }

    const focusNeighborhood = (node) => {
        if (!cy) return
        pathHighlightActive = false
        cy.elements().removeClass('dimmed focused path-active')
        const neighborhood = node.closedNeighborhood(':visible')
        cy.elements(':visible').addClass('dimmed')
        neighborhood.removeClass('dimmed').addClass('focused')
        node.select()
        selectedNodeId = node.id()
        updateEdgeLabelClasses()
    }

    const cloneTemplate = (templateId) => {
        const template = $(templateId)
        return template?.content?.firstElementChild?.cloneNode(true) || null
    }

    const text = (root, selector, value) => {
        const element = root?.querySelector(selector)
        if (element) element.textContent = value ?? ''
        return element
    }

    const statusTone = (value) => (['healthy', 'warning', 'critical', 'info'].includes(value) ? value : 'unknown')

    const applyStatusSurface = (label, dot, tone) => {
        const normalized = statusTone(tone)
        const allClasses = Object.values(statusSurfaceClasses).flat()
        label?.classList.remove(...allClasses)
        dot?.classList.remove(...allClasses)
        const [surfaceClass, textClass, dotClass] = statusSurfaceClasses[normalized]
        label?.classList.add(surfaceClass, textClass)
        dot?.classList.add(dotClass)
    }

    const renderEmptyInspector = () => {
        if (!detailContent) return
        detailContent.replaceChildren(cloneTemplate('topology-inspector-empty-template'))
        window.lucide?.createIcons()
    }

    const renderValueRows = (container, fields) => {
        container?.replaceChildren()
        fields.forEach((field) => {
            const normalizedLabel = String(field.label || '')
                .trim()
                .toLowerCase()
            const row = cloneTemplate('topology-field-row-template')
            if (!row) return
            text(row, '[data-field-label]', field.label)
            const displayValue = normalizedLabel === 'status' ? titleCaseText(field.value) : field.value
            const valueElement = text(row, '[data-field-value]', displayValue || 'Not Reported')
            if (normalizedLabel === 'api server' && valueElement) {
                valueElement.classList.remove('break-words')
                valueElement.classList.add('min-w-0', 'flex-1', 'truncate', 'whitespace-nowrap')
                valueElement.title = String(displayValue || 'Not Reported')
            }
            container.appendChild(row)
        })
    }

    const renderRelationshipRows = (container, node) => {
        container?.replaceChildren()
        const edges = node.connectedEdges(':visible')
        if (!edges.length) {
            container?.appendChild(cloneTemplate('topology-relationships-empty-template'))
            return
        }
        edges.forEach((edge) => {
            const sourceSelected = edge.source().id() === node.id()
            const peer = sourceSelected ? edge.target() : edge.source()
            const edgeData = edge.data()
            const ui = getRelationshipUi(edgeData.relationship)
            const row = cloneTemplate('topology-relationship-row-template')
            if (!row) return
            row.dataset.topologyRelatedNode = peer.id()
            row.querySelector('[data-relationship-icon]')?.setAttribute('data-lucide', ui.icon)
            text(row, '[data-relationship-direction]', sourceSelected ? 'Outbound' : 'Inbound')
            text(row, '[data-relationship-label]', titleCaseText(edgeData.label || edgeData.relationship))
            text(row, '[data-relationship-peer]', peer.data('label') || peer.id())
            text(row, '[data-relationship-peer-type]', humanizeType(peer.data('type')))
            row.addEventListener('click', () => selectNodeById(peer.id(), 'relationships'))
            container.appendChild(row)
        })
    }

    const drawDrawerMiniMap = () => {
        drawerMiniMapFrame = null
        if (!cy || !selectedNodeId) return

        const miniMap = detailContent?.querySelector('#topology-drawer-minimap')
        const selectedNode = cy.getElementById(selectedNodeId)
        if (!miniMap || !selectedNode?.length || selectedNode.data('type') !== 'cluster') return

        const clusterId = selectedNode.data('cluster_id')
        const clusterName = selectedNode.data('cluster_name') || selectedNode.data('label')
        const clusterNodes = cy
            .nodes(':visible')
            .filter(
                (item) =>
                    item.id() === selectedNode.id() ||
                    (clusterId && item.data('cluster_id') === clusterId) ||
                    (!clusterId && item.data('cluster_name') === clusterName)
            )
        if (!clusterNodes.length) return

        const nodeIds = new Set(clusterNodes.map((item) => item.id()))
        const clusterEdges = cy
            .edges(':visible')
            .filter((edge) => nodeIds.has(edge.source().id()) && nodeIds.has(edge.target().id()))

        const logicalWidth = Math.max(180, miniMap.clientWidth || 220)
        const logicalHeight = 144
        const pixelRatio = Math.max(1, window.devicePixelRatio || 1)
        miniMap.width = Math.round(logicalWidth * pixelRatio)
        miniMap.height = Math.round(logicalHeight * pixelRatio)
        miniMap.style.height = `${logicalHeight}px`

        const ctx = miniMap.getContext('2d')
        if (!ctx) return
        ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
        ctx.clearRect(0, 0, logicalWidth, logicalHeight)

        ctx.fillStyle = cssToken('--kaori-surface-card', 'Canvas')
        ctx.fillRect(0, 0, logicalWidth, logicalHeight)

        const positions = clusterNodes.map((item) => item.position())
        let minX = Math.min(...positions.map((position) => position.x))
        let maxX = Math.max(...positions.map((position) => position.x))
        let minY = Math.min(...positions.map((position) => position.y))
        let maxY = Math.max(...positions.map((position) => position.y))

        if (maxX - minX < 1) {
            minX -= 1
            maxX += 1
        }
        if (maxY - minY < 1) {
            minY -= 1
            maxY += 1
        }

        const padding = 14
        const scale = Math.min(
            (logicalWidth - padding * 2) / (maxX - minX),
            (logicalHeight - padding * 2) / (maxY - minY)
        )
        const graphWidth = (maxX - minX) * scale
        const graphHeight = (maxY - minY) * scale
        const offsetX = (logicalWidth - graphWidth) / 2
        const offsetY = (logicalHeight - graphHeight) / 2
        const mapPoint = (position) => ({
            x: offsetX + (position.x - minX) * scale,
            y: offsetY + (position.y - minY) * scale,
        })

        ctx.lineWidth = 1
        ctx.strokeStyle = cssToken('--kaori-outline-strong', 'GrayText')
        clusterEdges.forEach((edge) => {
            const source = mapPoint(edge.source().position())
            const target = mapPoint(edge.target().position())
            ctx.beginPath()
            ctx.moveTo(source.x, source.y)
            ctx.lineTo(target.x, target.y)
            ctx.stroke()
        })

        clusterNodes.forEach((item) => {
            const point = mapPoint(item.position())
            const visual = getTypeVisual(item.data('type'))
            const selected = item.id() === selectedNode.id()
            ctx.beginPath()
            ctx.arc(point.x, point.y, selected ? 5 : 3.25, 0, Math.PI * 2)
            ctx.fillStyle = visual.fill
            ctx.fill()
            ctx.lineWidth = selected ? 2 : 1
            ctx.strokeStyle = selected ? cssToken('--kaori-brand-primary', 'CanvasText') : visual.border
            ctx.stroke()
        })

        const extent = cy.extent()
        const topLeft = mapPoint({ x: extent.x1, y: extent.y1 })
        const bottomRight = mapPoint({ x: extent.x2, y: extent.y2 })
        const viewportX = Math.max(1, Math.min(topLeft.x, bottomRight.x))
        const viewportY = Math.max(1, Math.min(topLeft.y, bottomRight.y))
        const viewportWidth = Math.min(logicalWidth - viewportX - 1, Math.abs(bottomRight.x - topLeft.x))
        const viewportHeight = Math.min(logicalHeight - viewportY - 1, Math.abs(bottomRight.y - topLeft.y))
        ctx.strokeStyle = cssToken('--kaori-status-info', 'CanvasText')
        ctx.lineWidth = 1.5
        ctx.setLineDash([4, 3])
        ctx.strokeRect(viewportX, viewportY, Math.max(4, viewportWidth), Math.max(4, viewportHeight))
        ctx.setLineDash([])

        miniMap._kaoriMiniMap = {
            minX,
            minY,
            scale,
            offsetX,
            offsetY,
            logicalWidth,
            logicalHeight,
            clusterNodes,
        }

        if (!miniMap.dataset.kaoriBound) {
            miniMap.dataset.kaoriBound = 'true'
            miniMap.addEventListener('click', (event) => {
                const state = miniMap._kaoriMiniMap
                if (!state || !cy) return
                const rect = miniMap.getBoundingClientRect()
                const logicalX = (event.clientX - rect.left) * (state.logicalWidth / rect.width)
                const logicalY = (event.clientY - rect.top) * (state.logicalHeight / rect.height)
                const graphX = (logicalX - state.offsetX) / state.scale + state.minX
                const graphY = (logicalY - state.offsetY) / state.scale + state.minY
                let nearest = null
                let nearestDistance = Number.POSITIVE_INFINITY
                state.clusterNodes.forEach((item) => {
                    const position = item.position()
                    const distance = Math.hypot(position.x - graphX, position.y - graphY)
                    if (distance < nearestDistance) {
                        nearest = item
                        nearestDistance = distance
                    }
                })
                if (nearest?.length) {
                    cy.animate({ center: { eles: nearest } }, { duration: 220 })
                }
            })
        }
    }

    const scheduleDrawerMiniMapUpdate = () => {
        if (drawerMiniMapFrame) cancelAnimationFrame(drawerMiniMapFrame)
        drawerMiniMapFrame = requestAnimationFrame(drawDrawerMiniMap)
    }

    const renderNodeDetails = (node, initialTab = activeDrawerTab) => {
        if (!detailContent) return
        selectedNodeId = node.id()
        activeDrawerTab = initialTab === 'relationships' ? 'relationships' : 'details'
        const data = node.data()
        const ui = getTypeUi(data.type)
        const childCount = descendantsOf(node.id()).size
        const isCollapsed = collapsedNodeIds.has(node.id())
        const connectedCount = node.connectedEdges(':visible').length
        const view = cloneTemplate('topology-node-inspector-template')
        if (!view) return

        view.querySelector('[data-node-icon]')?.setAttribute('data-lucide', ui.icon)
        view.querySelector('[data-node-icon-shell]')?.classList.add(`kaori-topology-domain-${ui.domain}`)
        text(view, '[data-node-label]', data.label)
        text(view, '[data-node-kind]', data.kind || humanizeType(data.type))
        text(view, '[data-node-type]', humanizeType(data.type))
        text(view, '[data-node-status-text]', titleCaseText(data.status || 'Unknown'))
        applyStatusSurface(
            view.querySelector('[data-node-status]'),
            view.querySelector('[data-node-status-dot]'),
            data.status_tone
        )
        const description = view.querySelector('[data-node-description]')
        if (description && data.description) {
            description.textContent = data.description
            description.classList.remove('hidden')
        }

        text(view, '[data-highlight-label]', pathHighlightActive ? 'Clear Path' : 'Highlight Path')
        const collapseButton = view.querySelector('#topology-collapse-button')
        collapseButton.disabled = !childCount
        view.querySelector('[data-collapse-icon]')?.setAttribute(
            'data-lucide',
            isCollapsed ? 'unfold-vertical' : 'fold-vertical'
        )
        text(
            view,
            '[data-collapse-label]',
            childCount ? (isCollapsed ? `Expand ${childCount}` : `Collapse ${childCount}`) : 'No Loaded Children'
        )

        const fields = [
            { label: 'Cluster', value: data.cluster_name || 'Not Reported' },
            { label: 'Namespace', value: data.namespace || 'Cluster Scoped' },
            ...(Array.isArray(data.fields) ? data.fields : []),
            { label: 'Collected At', value: formatDateTime(data.collected_at) },
        ]
        renderValueRows(view.querySelector('[data-node-fields]'), fields)

        const minimap = view.querySelector('[data-node-minimap]')
        minimap?.classList.toggle('hidden', data.type !== 'cluster')
        const action = view.querySelector('[data-node-action]')
        if (action && data.action_url) {
            action.href = data.action_url
            action.classList.remove('hidden')
            action.classList.add('inline-flex')
        }

        const tabButtons = Array.from(view.querySelectorAll('[data-kaori-segmented-group="topology-inspector"]'))
        const detailsPanelLocal = view.querySelector('#topology-inspector-panel-details')
        const relationshipsPanel = view.querySelector('#topology-inspector-panel-relationships')
        const activateTab = (tab) => {
            activeDrawerTab = tab === 'relationships' ? 'relationships' : 'details'
            tabButtons.forEach((button) => {
                const active = button.dataset.kaoriSegmentedTab === activeDrawerTab
                button.setAttribute('aria-selected', active ? 'true' : 'false')
                button.tabIndex = active ? 0 : -1
                button.classList.toggle('bg-surface-card', active)
                button.classList.toggle('text-kaori-primary', active)
                button.classList.toggle('shadow-sm', active)
                button.classList.toggle('text-content-muted', !active)
            })
            detailsPanelLocal.hidden = activeDrawerTab !== 'details'
            relationshipsPanel.hidden = activeDrawerTab !== 'relationships'
            if (activeDrawerTab === 'relationships')
                renderRelationshipRows(relationshipsPanel.querySelector('[data-node-relationships]'), node)
            if (activeDrawerTab === 'details') scheduleDrawerMiniMapUpdate()
            window.lucide?.createIcons()
        }
        tabButtons.forEach((button) =>
            button.addEventListener('click', () => activateTab(button.dataset.kaoriSegmentedTab))
        )
        bindSegmentedKeyboard(tabButtons, (button) => activateTab(button.dataset.kaoriSegmentedTab))
        view.querySelector('#topology-highlight-path-button')?.addEventListener('click', () => {
            if (pathHighlightActive) {
                clearPathHighlight()
                renderNodeDetails(node, activeDrawerTab)
            } else {
                highlightPaths(node)
            }
        })
        collapseButton?.addEventListener('click', () => {
            if (!childCount) return
            if (isCollapsed) collapsedNodeIds.delete(node.id())
            else collapsedNodeIds.add(node.id())
            applyVisibility({ relayout: true })
            const refreshed = cy.getElementById(node.id())
            if (refreshed?.length) renderNodeDetails(refreshed, activeDrawerTab)
        })

        detailContent.replaceChildren(view)
        activateTab(activeDrawerTab)
        openPane(detailsPanel)
        window.lucide?.createIcons()
    }

    const renderEdgeDetails = (edge) => {
        if (!detailContent) return
        selectedNodeId = null
        pathHighlightActive = false
        const data = edge.data()
        const ui = getRelationshipUi(data.relationship)
        const view = cloneTemplate('topology-edge-inspector-template')
        if (!view) return
        view.querySelector('[data-edge-icon]')?.setAttribute('data-lucide', ui.icon)
        text(view, '[data-edge-title]', data.label || 'Relationship')
        text(view, '[data-edge-type]', titleCaseText(data.relationship))
        text(view, '[data-edge-source]', data.source_label)
        text(view, '[data-edge-label]', data.label)
        text(view, '[data-edge-target]', data.target_label)
        const swatch = view.querySelector('[data-edge-swatch]')
        if (swatch) swatch.style.backgroundColor = edgeColor(data.relationship)
        const description = view.querySelector('[data-edge-description]')
        if (description && data.description) {
            description.textContent = data.description
            description.classList.remove('hidden')
        }
        detailContent.replaceChildren(view)
        openPane(detailsPanel)
        window.lucide?.createIcons()
    }

    const renderPayloadRelationshipRows = (container, nodeId) => {
        container?.replaceChildren()
        const nodeMap = new Map((currentPayload.nodes || []).map((item) => [item?.data?.id, item?.data || {}]))
        const edges = (currentPayload.edges || []).filter((item) => {
            const data = item?.data || {}
            return data.source === nodeId || data.target === nodeId
        })
        if (!edges.length) {
            container?.appendChild(cloneTemplate('topology-relationships-empty-template'))
            return
        }
        edges.forEach((item) => {
            const data = item.data || {}
            const sourceSelected = data.source === nodeId
            const peerId = sourceSelected ? data.target : data.source
            const peer = nodeMap.get(peerId) || {}
            const ui = getRelationshipUi(data.relationship)
            const row = cloneTemplate('topology-relationship-row-template')
            if (!row) return
            row.dataset.topologyRelatedNode = peerId || ''
            row.querySelector('[data-relationship-icon]')?.setAttribute('data-lucide', ui.icon)
            text(row, '[data-relationship-direction]', sourceSelected ? 'Outbound' : 'Inbound')
            text(row, '[data-relationship-label]', titleCaseText(data.label || data.relationship))
            text(row, '[data-relationship-peer]', peer.label || peerId || 'Unknown Resource')
            text(row, '[data-relationship-peer-type]', humanizeType(peer.type || 'resource'))
            if (peerId) row.addEventListener('click', () => selectNodeById(peerId, 'relationships'))
            else row.disabled = true
            container.appendChild(row)
        })
    }

    const renderPayloadNodeDetails = (data, initialTab = activeDrawerTab) => {
        if (!detailContent || !data) return
        selectedNodeId = data.id || null
        activeDrawerTab = initialTab === 'relationships' ? 'relationships' : 'details'
        const ui = getTypeUi(data.type)
        const view = cloneTemplate('topology-node-inspector-template')
        if (!view) return

        view.querySelector('[data-node-icon]')?.setAttribute('data-lucide', ui.icon)
        view.querySelector('[data-node-icon-shell]')?.classList.add(`kaori-topology-domain-${ui.domain}`)
        text(view, '[data-node-label]', data.label || data.id || 'Inventory Resource')
        text(view, '[data-node-kind]', data.kind || humanizeType(data.type))
        text(view, '[data-node-type]', humanizeType(data.type))
        text(view, '[data-node-status-text]', titleCaseText(data.status || 'Unknown'))
        applyStatusSurface(
            view.querySelector('[data-node-status]'),
            view.querySelector('[data-node-status-dot]'),
            data.status_tone
        )
        const description = view.querySelector('[data-node-description]')
        if (description && data.description) {
            description.textContent = data.description
            description.classList.remove('hidden')
        }

        const highlightButton = view.querySelector('#topology-highlight-path-button')
        const collapseButton = view.querySelector('#topology-collapse-button')
        ;[highlightButton, collapseButton].forEach((button) => {
            if (!button) return
            button.disabled = true
            button.classList.add('cursor-not-allowed', 'opacity-45')
        })
        text(view, '[data-highlight-label]', 'Graph Renderer Required')
        view.querySelector('[data-collapse-icon]')?.setAttribute('data-lucide', 'fold-vertical')
        text(view, '[data-collapse-label]', 'Graph Renderer Required')

        const fields = [
            { label: 'Cluster', value: data.cluster_name || 'Not Reported' },
            { label: 'Namespace', value: data.namespace || 'Cluster Scoped' },
            ...(Array.isArray(data.fields) ? data.fields : []),
            { label: 'Collected At', value: formatDateTime(data.collected_at) },
        ]
        renderValueRows(view.querySelector('[data-node-fields]'), fields)
        view.querySelector('[data-node-minimap]')?.classList.add('hidden')
        const action = view.querySelector('[data-node-action]')
        if (action && data.action_url) {
            action.href = data.action_url
            action.classList.remove('hidden')
            action.classList.add('inline-flex')
        }

        const tabButtons = Array.from(view.querySelectorAll('[data-kaori-segmented-group="topology-inspector"]'))
        const detailsPanelLocal = view.querySelector('#topology-inspector-panel-details')
        const relationshipsPanel = view.querySelector('#topology-inspector-panel-relationships')
        const activateTab = (tab) => {
            activeDrawerTab = tab === 'relationships' ? 'relationships' : 'details'
            tabButtons.forEach((button) => {
                const active = button.dataset.kaoriSegmentedTab === activeDrawerTab
                button.setAttribute('aria-selected', active ? 'true' : 'false')
                button.tabIndex = active ? 0 : -1
                button.classList.toggle('bg-surface-card', active)
                button.classList.toggle('text-kaori-primary', active)
                button.classList.toggle('shadow-sm', active)
                button.classList.toggle('text-content-muted', !active)
            })
            detailsPanelLocal.hidden = activeDrawerTab !== 'details'
            relationshipsPanel.hidden = activeDrawerTab !== 'relationships'
            if (activeDrawerTab === 'relationships') {
                renderPayloadRelationshipRows(relationshipsPanel.querySelector('[data-node-relationships]'), data.id)
            }
            window.lucide?.createIcons()
        }
        tabButtons.forEach((button) =>
            button.addEventListener('click', () => activateTab(button.dataset.kaoriSegmentedTab))
        )
        bindSegmentedKeyboard(tabButtons, (button) => activateTab(button.dataset.kaoriSegmentedTab))
        detailContent.replaceChildren(view)
        activateTab(activeDrawerTab)
        openPane(detailsPanel)
        window.lucide?.createIcons()
    }

    const clearSelection = () => {
        selectedNodeId = null
        pathHighlightActive = false
        if (cy) {
            cy.elements().removeClass('dimmed focused path-active edge-label-visible search-match')
            cy.elements().unselect()
            updateEdgeLabelClasses()
        }
        renderEmptyInspector()
    }

    const selectNodeById = (id, tab = 'details') => {
        if (!cy) {
            const data = (currentPayload.nodes || []).find((item) => item?.data?.id === id)?.data
            if (data) renderPayloadNodeDetails(data, tab)
            hideSearchResults()
            return
        }
        const node = cy.getElementById(id)
        if (!node?.length || !node.visible()) return
        focusNeighborhood(node)
        renderNodeDetails(node, tab)
        cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 1.05) }, { duration: 220 })
        hideSearchResults()
    }

    const attachGraphEvents = () => {
        cy.on('pan zoom position layoutstop', scheduleDrawerMiniMapUpdate)
        cy.on('tap', 'node', (event) => {
            focusNeighborhood(event.target)
            renderNodeDetails(event.target)
        })
        cy.on('dbltap', 'node', (event) => {
            const node = event.target
            if (!descendantsOf(node.id()).size) return
            if (collapsedNodeIds.has(node.id())) collapsedNodeIds.delete(node.id())
            else collapsedNodeIds.add(node.id())
            applyVisibility({ relayout: true })
            renderNodeDetails(node, activeDrawerTab)
        })
        cy.on('tap', 'edge', (event) => {
            clearPathHighlight({ preserveSelection: false })
            cy.elements().unselect()
            event.target.select().addClass('edge-label-visible')
            event.target.connectedNodes().addClass('focused')
            renderEdgeDetails(event.target)
        })
        cy.on('tap', (event) => {
            if (event.target === cy) clearSelection()
        })
        cy.on('mouseover', 'edge', (event) => event.target.addClass('edge-label-visible'))
        cy.on('mouseout', 'edge', (event) => {
            if (!workspaceState.edgeLabels && !event.target.selected() && !event.target.hasClass('path-active'))
                event.target.removeClass('edge-label-visible')
        })
        cy.on('mouseover', 'node', (event) => {
            if (!workspaceState.edgeLabels) event.target.connectedEdges(':visible').addClass('edge-label-visible')
        })
        cy.on('mouseout', 'node', () => updateEdgeLabelClasses())
        cy.on('pan zoom resize render position', () => {
            scheduleBoundaryUpdate()
        })
    }

    const applyCurrentLayout = () => {
        if (!cy) return
        const visible = visibleGraphElements()
        if (!visible || !visible.nodes().length) return
        let stopped = false
        const finalize = () => {
            if (stopped) return
            stopped = true
            window.requestAnimationFrame(() => {
                ensureCanvasDimensions()
                cy.resize()
                fitGraphToCanvas()
                scheduleBoundaryUpdate()
                window.setTimeout(fitGraphToCanvas, 140)
            })
        }
        cy.one('layoutstop', finalize)
        visible.layout(layoutOptions()).run()
        window.setTimeout(finalize, 700)
    }

    const updateActiveSearchOption = () => {
        const options = Array.from(searchResults?.querySelectorAll('[role="option"]') || [])
        options.forEach((option, index) => {
            const active = index === activeSearchIndex
            option.setAttribute('aria-selected', active ? 'true' : 'false')
            option.classList.toggle('bg-kaori-soft', active)
        })
        const activeOption = options[activeSearchIndex]
        if (activeOption) {
            searchInput.setAttribute('aria-activedescendant', activeOption.id)
            activeOption.scrollIntoView({ block: 'nearest' })
        } else {
            searchInput.removeAttribute('aria-activedescendant')
        }
    }

    const renderSearchResults = (term) => {
        if (!searchResults) return
        const normalized = String(term || '')
            .trim()
            .toLowerCase()
        cy?.nodes().removeClass('search-match')
        searchResults.replaceChildren()
        searchResultNodes = []
        activeSearchIndex = -1
        if (!normalized) {
            hideSearchResults()
            if (searchSummary) searchSummary.textContent = 'Search and open a resource in the current topology scope.'
            return
        }
        const matches = visibleNodeRecords()
            .filter((node) => {
                const data = node.data()
                return [data.label, data.kind, data.type, data.cluster_name, data.namespace, data.status]
                    .filter(Boolean)
                    .join(' ')
                    .toLowerCase()
                    .includes(normalized)
            })
            .sort((a, b) => {
                const aLabel = String(a.data('label') || '').toLowerCase()
                const bLabel = String(b.data('label') || '').toLowerCase()
                return (
                    Number(bLabel.startsWith(normalized)) - Number(aLabel.startsWith(normalized)) ||
                    aLabel.localeCompare(bLabel)
                )
            })
        if (cy) {
            matches.forEach((node) => cy.getElementById(node.id()).addClass('search-match'))
        }
        searchResultNodes = matches.slice(0, 8)
        if (!searchResultNodes.length) {
            const empty = document.createElement('div')
            empty.className = 'px-3 py-3 text-xs text-content-muted'
            empty.textContent = 'No matching resource in the current topology.'
            searchResults.appendChild(empty)
        } else {
            searchResultNodes.forEach((node, index) => {
                const data = node.data()
                const ui = getTypeUi(data.type)
                const button = document.createElement('button')
                button.type = 'button'
                button.id = `topology-search-option-${index}`
                button.setAttribute('role', 'option')
                button.setAttribute('aria-selected', 'false')
                button.className =
                    'flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition hover:bg-kaori-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-focus'
                const iconShell = document.createElement('span')
                iconShell.className = `flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border kaori-topology-domain-${ui.domain}`
                const icon = document.createElement('i')
                icon.setAttribute('data-lucide', ui.icon)
                icon.className = 'h-4 w-4'
                iconShell.appendChild(icon)
                const copy = document.createElement('span')
                copy.className = 'min-w-0 flex-1'
                const title = document.createElement('span')
                title.className = 'block truncate text-xs font-medium text-content-primary'
                title.textContent = data.label
                const helper = document.createElement('span')
                helper.className = 'mt-1 block truncate text-xs text-content-muted'
                helper.textContent = `${humanizeType(data.type)}${data.namespace ? ` · ${data.namespace}` : ''} · ${data.cluster_name || 'Unknown Cluster'}`
                copy.append(title, helper)
                button.append(iconShell, copy)
                button.addEventListener('click', () => selectNodeById(node.id()))
                searchResults.appendChild(button)
            })
        }
        searchResults.classList.remove('hidden')
        searchInput.setAttribute('aria-expanded', 'true')
        if (searchSummary)
            searchSummary.textContent = `${matches.length} matching ${matches.length === 1 ? 'resource' : 'resources'} found.`
        window.lucide?.createIcons()
    }

    const hideSearchResults = () => {
        searchResults?.classList.add('hidden')
        searchInput?.setAttribute('aria-expanded', 'false')
        searchInput?.removeAttribute('aria-activedescendant')
        activeSearchIndex = -1
    }

    const scheduleBoundaryUpdate = () => {
        if (boundaryFrame) cancelAnimationFrame(boundaryFrame)
        boundaryFrame = requestAnimationFrame(updateNamespaceBoundaries)
    }

    const updateNamespaceBoundaries = () => {
        boundaryFrame = null
        if (!boundaryLayer) return
        boundaryLayer.replaceChildren()
        if (!cy || !workspaceState.groupByNamespace) return
        const groups = new Map()
        cy.nodes(':visible').forEach((node) => {
            const namespace = node.data('namespace')
            if (!namespace || node.data('type') === 'cluster' || node.data('type') === 'node') return
            const key = `${node.data('cluster_id')}::${namespace}`
            if (!groups.has(key)) groups.set(key, { namespace, nodes: cy.collection() })
            groups.get(key).nodes = groups.get(key).nodes.union(node)
        })
        groups.forEach(({ namespace, nodes }) => {
            if (!nodes.length) return
            const box = nodes.renderedBoundingBox({ includeLabels: true, includeOverlays: false })
            const padding = 20
            const boundary = document.createElement('div')
            boundary.className = 'absolute rounded-xl border border-dashed border-outline-focus bg-kaori-soft/40'
            boundary.style.left = `${box.x1 - padding}px`
            boundary.style.top = `${box.y1 - padding}px`
            boundary.style.width = `${box.w + padding * 2}px`
            boundary.style.height = `${box.h + padding * 2}px`
            const label = document.createElement('span')
            label.className =
                'absolute -top-3 left-3 rounded-md border border-outline-default bg-surface-card px-2 py-0.5 text-xs font-semibold text-kaori-primary shadow-sm'
            label.textContent = namespace
            boundary.appendChild(label)
            boundaryLayer.appendChild(boundary)
        })
    }

    const downloadBlob = (blob, filename) => {
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement('a')
        anchor.href = url
        anchor.download = filename
        document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        URL.revokeObjectURL(url)
    }

    const exportJson = () => {
        const visibleNodes = visibleNodeRecords().map((node) => node.data())
        const visibleIds = new Set(visibleNodes.map((node) => node.id))
        const visibleEdges = cy
            ? cy.edges(':visible').map((edge) => edge.data())
            : (currentPayload.edges || [])
                  .map((edge) => edge?.data || {})
                  .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
        const payload = {
            product: 'KAORI',
            generated_at: new Date().toISOString(),
            filters: {
                cluster_id: clusterSelect.value,
                namespace: namespaceSelect.value,
                scope: scopeSelect.value,
                depth: depthSelect.value,
                layout: getLayoutMode(),
                view: activeView,
            },
            summary: currentPayload.summary || {},
            nodes: visibleNodes,
            edges: visibleEdges,
        }
        downloadBlob(
            new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }),
            `kaori-topology-${Date.now()}.json`
        )
    }

    const exportPng = () => {
        if (!cy) return
        const dataUrl = cy.png({ full: true, scale: 2, bg: cssToken('--kaori-surface-card', 'white') })
        const image = new Image()
        image.onload = () => {
            const footer = 42
            const output = document.createElement('canvas')
            output.width = image.width
            output.height = image.height + footer
            const ctx = output.getContext('2d')
            ctx.fillStyle = cssToken('--kaori-surface-card', 'white')
            ctx.fillRect(0, 0, output.width, output.height)
            ctx.drawImage(image, 0, 0)
            ctx.fillStyle = cssToken('--kaori-content-secondary', 'GrayText')
            ctx.font = '24px sans-serif'
            const collected = currentPayload.summary?.last_collected_at
                ? formatDateTime(currentPayload.summary.last_collected_at)
                : 'No snapshot timestamp'
            ctx.fillText(`KAORI · Kubernetes Topology · ${collected}`, 18, image.height + 29)
            output.toBlob((blob) => {
                if (blob) downloadBlob(blob, `kaori-topology-${Date.now()}.png`)
            }, 'image/png')
        }
        image.src = dataUrl
    }

    const setLoading = (state) => {
        loading?.classList.toggle('htmx-request', state)
        const reload = $('topology-reload-button')
        if (reload) reload.disabled = state
    }

    const createGraph = (payload) => {
        currentPayload = payload
        if (cy) cy.destroy()
        if (!topologyRenderer) {
            cy = null
            const graphTab = viewTabs.find((button) => button.dataset.kaoriSegmentedTab === 'graph')
            if (graphTab) {
                graphTab.disabled = true
                graphTab.setAttribute('aria-disabled', 'true')
            }
            updateSummary(payload)
            renderEmptyInspector()
            renderResourceList()
            setRuntimeStatus()
            showError(
                'The graph renderer is unavailable. Resource List remains available from the committed inventory snapshot.'
            )
            const pngButton = $('topology-export-png-button')
            if (pngButton) pngButton.disabled = true
            setActiveView('list')
            return
        }
        const graphTab = viewTabs.find((button) => button.dataset.kaoriSegmentedTab === 'graph')
        if (graphTab) {
            graphTab.disabled = false
            graphTab.removeAttribute('aria-disabled')
        }
        collapsedNodeIds = new Set()
        collapsedHiddenIds = new Set()
        selectedNodeId = null
        pathHighlightActive = false
        renderEmptyInspector()
        const prepared = prepareElements(payload)
        const hasNodes = prepared.nodes.length > 0
        emptyState?.classList.toggle('hidden', hasNodes)
        emptyState?.classList.toggle('flex', !hasNodes)
        updateSummary(payload)
        if (!hasNodes) {
            cy = null
            renderResourceList()
            setRuntimeStatus()
            return
        }
        ensureCanvasDimensions()
        setRuntimeStatus(`Rendering ${prepared.nodes.length} resources and ${prepared.edges.length} relationships...`)
        try {
            cy = topologyRenderer({
                container: canvas,
                elements: prepared.elements,
                layout: { name: 'preset' },
                maxZoom: 2.6,
                minZoom: 0.12,
                pixelRatio: 'auto',
                selectionType: 'single',
                style: graphStyle(),
            })
            buildHierarchyIndex()
            attachGraphEvents()
            applyVisibility()
            renderResourceList()

            let finalized = false
            const finalize = () => {
                if (finalized) return
                finalized = true
                window.requestAnimationFrame(() => {
                    ensureCanvasDimensions()
                    cy.resize()
                    fitGraphToCanvas()
                    window.setTimeout(fitGraphToCanvas, 120)
                    window.setTimeout(fitGraphToCanvas, 320)
                    scheduleBoundaryUpdate()
                    setRuntimeStatus()
                    showError()
                })
            }

            const visible = visibleGraphElements()
            const layout = visible && visible.nodes().length ? visible.layout(layoutOptions()) : null
            if (layout) {
                cy.one('layoutstop', finalize)
                layout.run()
                window.setTimeout(finalize, 700)
            } else {
                finalize()
            }
        } catch (error) {
            console.error('KAORI could not render topology.', error)
            cy = null
            setRuntimeStatus()
            showError(`Topology renderer failed: ${error.message || 'unknown error'}`)
        }
    }

    const fetchGraph = async () => {
        fetchController?.abort()
        fetchController = new AbortController()
        setLoading(true)
        showError()
        const params = new URLSearchParams({
            cluster_id: clusterSelect.value,
            namespace: namespaceSelect.disabled ? '' : namespaceSelect.value,
            scope: scopeSelect.value,
            depth: depthSelect.value,
        })
        try {
            const response = await fetch(`${config.data_url}?${params.toString()}`, {
                credentials: 'same-origin',
                headers: { Accept: 'application/json' },
                signal: fetchController.signal,
            })
            if (!response.ok) throw new Error(`Topology request failed with HTTP ${response.status}.`)
            createGraph(await response.json())
            updateUrl()
        } catch (error) {
            if (error.name !== 'AbortError') showError(error.message || 'KAORI could not load topology data.')
        } finally {
            setLoading(false)
        }
    }

    applyStateToControls()
    syncLayoutFromUrl()
    updateNamespaceOptions(config.filters?.namespace || '')
    createGraph(currentPayload)
    setActiveView(activeView, { updateUrl: false })
    syncClearFiltersVisibility()

    const reloadForFilterChange = () => {
        syncClearFiltersVisibility()
        fetchGraph()
    }

    clusterSelect.addEventListener('change', () => {
        updateNamespaceOptions('')
        reloadForFilterChange()
    })
    namespaceSelect.addEventListener('change', reloadForFilterChange)
    scopeSelect.addEventListener('change', reloadForFilterChange)
    depthSelect.addEventListener('change', reloadForFilterChange)
    layoutModeSelect?.addEventListener('change', () => {
        updateUrl()
        applyCurrentLayout()
    })

    nodeLabelToggle?.addEventListener('change', () => {
        workspaceState.nodeLabels = nodeLabelToggle.checked
        saveWorkspaceState()
        if (cy)
            cy.style()
                .selector('node')
                .style('label', workspaceState.nodeLabels ? 'data(display_label)' : '')
                .update()
        scheduleBoundaryUpdate()
    })

    edgeLabelToggle?.addEventListener('change', () => {
        workspaceState.edgeLabels = edgeLabelToggle.checked
        saveWorkspaceState()
        updateEdgeLabelClasses()
    })

    groupNamespaceToggle?.addEventListener('change', () => {
        workspaceState.groupByNamespace = groupNamespaceToggle.checked
        saveWorkspaceState()
        scheduleBoundaryUpdate()
    })

    resourceToggles.forEach((toggle) =>
        toggle.addEventListener('change', () => {
            workspaceState.resources[toggle.dataset.topologyResourceToggle] = toggle.checked
            saveWorkspaceState()
            applyVisibility({ relayout: true })
        })
    )

    relationshipToggles.forEach((toggle) =>
        toggle.addEventListener('change', () => {
            workspaceState.relationships[toggle.dataset.topologyRelationshipToggle] = toggle.checked
            saveWorkspaceState()
            applyVisibility({ relayout: getLayoutMode() === 'dependency' })
        })
    )

    searchInput.addEventListener('input', () => {
        syncClearFiltersVisibility()
        window.clearTimeout(searchTimer)
        searchTimer = window.setTimeout(() => renderSearchResults(searchInput.value), 160)
    })
    searchInput.addEventListener('focus', () => renderSearchResults(searchInput.value))
    searchInput.addEventListener('keydown', (event) => {
        if (!searchResultNodes.length && !['Escape'].includes(event.key)) return
        if (event.key === 'ArrowDown') {
            event.preventDefault()
            activeSearchIndex = Math.min(activeSearchIndex + 1, searchResultNodes.length - 1)
            updateActiveSearchOption()
        } else if (event.key === 'ArrowUp') {
            event.preventDefault()
            activeSearchIndex = Math.max(activeSearchIndex - 1, 0)
            updateActiveSearchOption()
        } else if (event.key === 'Enter' && activeSearchIndex >= 0) {
            event.preventDefault()
            selectNodeById(searchResultNodes[activeSearchIndex].id())
        } else if (event.key === 'Escape') {
            hideSearchResults()
        }
    })
    document.addEventListener('click', (event) => {
        if (!searchResults?.contains(event.target) && event.target !== searchInput) hideSearchResults()
    })

    viewTabs.forEach((button) => button.addEventListener('click', () => setActiveView(button.dataset.kaoriSegmentedTab)))
    bindSegmentedKeyboard(viewTabs, (button) => setActiveView(button.dataset.kaoriSegmentedTab))
    $('topology-controls-button')?.addEventListener('click', () => openPane(controlsPanel))
    $('topology-details-button')?.addEventListener('click', () => openPane(detailsPanel))
    paneBackdrop?.addEventListener('click', closePanes)
    document
        .querySelectorAll('[data-topology-close-pane]')
        .forEach((button) => button.addEventListener('click', closePanes))
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closePanes()
    })

    $('topology-fit-button')?.addEventListener('click', fitGraphToCanvas)
    $('topology-reset-button')?.addEventListener('click', () => {
        collapsedNodeIds = new Set()
        clearSelection()
        applyVisibility({ relayout: true })
    })
    $('topology-reload-button')?.addEventListener('click', fetchGraph)
    clearFiltersButton?.addEventListener('click', (event) => {
        event.preventDefault()
        clusterSelect.value = ''
        updateNamespaceOptions('')
        scopeSelect.value = 'all'
        depthSelect.value = '1'
        searchInput.value = ''
        hideSearchResults()
        collapsedNodeIds = new Set()
        clearSelection()
        if (searchSummary) searchSummary.textContent = 'Search and open a resource in the current topology scope.'
        syncClearFiltersVisibility()
        fetchGraph()
    })
    $('topology-export-png-button')?.addEventListener('click', exportPng)
    $('topology-export-json-button')?.addEventListener('click', exportJson)

    if (window.ResizeObserver && canvasShell) {
        const observer = new ResizeObserver(() => {
            if (!cy) return
            cy.resize()
            scheduleBoundaryUpdate()
            scheduleDrawerMiniMapUpdate()
        })
        observer.observe(canvasShell)
    }

    $('theme-toggle')?.addEventListener('click', () =>
        window.setTimeout(() => {
            if (!cy) return
            cy.style(graphStyle())
            scheduleBoundaryUpdate()
            scheduleDrawerMiniMapUpdate()
        }, 0)
    )
}

startTopologyWorkspace()
