(() => {
    const config = window.KAORI_TOPOLOGY
    if (!config) return

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

    if (!canvas || !clusterSelect || !namespaceSelect || !scopeSelect || !depthSelect) return

    const STATE_KEY = 'kaori.topology.workspace.v4'
    const resourceTypes = ['cluster', 'namespace', 'node', 'workload', 'pod', 'service', 'ingress', 'configmap', 'secret', 'pvc', 'pv']
    const relationshipTypes = ['contains', 'owns', 'scheduled_on', 'selects', 'routes_to', 'uses', 'mounts', 'binds']

    let cy = null
    let currentPayload = config.initial_graph || { nodes: [], edges: [], summary: {}, type_counts: {} }
    let fetchController = null
    let searchTimer = null
    let selectedNodeId = null
    let activeDrawerTab = 'details'
    let pathHighlightActive = false
    let boundaryFrame = null
    let collapsedNodeIds = new Set()
    let collapsedHiddenIds = new Set()
    let childrenByNode = new Map()

    const typeVisuals = {
        cluster: { fill: '#2563eb', border: '#1d4ed8', text: '#ffffff' },
        namespace: { fill: '#4f46e5', border: '#4338ca', text: '#ffffff' },
        node: { fill: '#475569', border: '#334155', text: '#ffffff' },
        workload: { fill: '#7c3aed', border: '#6d28d9', text: '#ffffff' },
        pod: { fill: '#cffafe', border: '#06b6d4', text: '#155e75' },
        service: { fill: '#059669', border: '#047857', text: '#ffffff' },
        ingress: { fill: '#0f766e', border: '#115e59', text: '#ffffff' },
        configmap: { fill: '#0284c7', border: '#0369a1', text: '#ffffff' },
        secret: { fill: '#fef3c7', border: '#f59e0b', text: '#92400e' },
        pvc: { fill: '#ea580c', border: '#c2410c', text: '#ffffff' },
        pv: { fill: '#ecfccb', border: '#84cc16', text: '#3f6212' },
    }

    const typeUi = {
        cluster: { icon: 'server-cog', value: 'text-blue-700 dark:text-blue-300', badge: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300', iconClass: 'bg-blue-100 text-blue-700 ring-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20' },
        namespace: { icon: 'layers-3', value: 'text-indigo-700 dark:text-indigo-300', badge: 'border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-500/20 dark:bg-indigo-500/10 dark:text-indigo-300', iconClass: 'bg-indigo-100 text-indigo-700 ring-indigo-200 dark:bg-indigo-500/10 dark:text-indigo-300 dark:ring-indigo-500/20' },
        node: { icon: 'server', value: 'text-slate-700 dark:text-slate-300', badge: 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-600 dark:bg-slate-700/40 dark:text-slate-300', iconClass: 'bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-700/60 dark:text-slate-300 dark:ring-slate-600' },
        workload: { icon: 'boxes', value: 'text-violet-700 dark:text-violet-300', badge: 'border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/20 dark:bg-violet-500/10 dark:text-violet-300', iconClass: 'bg-violet-100 text-violet-700 ring-violet-200 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/20' },
        pod: { icon: 'circle-dot', value: 'text-cyan-700 dark:text-cyan-300', badge: 'border-cyan-200 bg-cyan-50 text-cyan-700 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-300', iconClass: 'bg-cyan-100 text-cyan-700 ring-cyan-200 dark:bg-cyan-500/10 dark:text-cyan-300 dark:ring-cyan-500/20' },
        service: { icon: 'network', value: 'text-emerald-700 dark:text-emerald-300', badge: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300', iconClass: 'bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20' },
        ingress: { icon: 'route', value: 'text-teal-700 dark:text-teal-300', badge: 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-500/20 dark:bg-teal-500/10 dark:text-teal-300', iconClass: 'bg-teal-100 text-teal-700 ring-teal-200 dark:bg-teal-500/10 dark:text-teal-300 dark:ring-teal-500/20' },
        configmap: { icon: 'file-cog', value: 'text-sky-700 dark:text-sky-300', badge: 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300', iconClass: 'bg-sky-100 text-sky-700 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/20' },
        secret: { icon: 'key-round', value: 'text-amber-700 dark:text-amber-300', badge: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300', iconClass: 'bg-amber-100 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20' },
        pvc: { icon: 'database', value: 'text-orange-700 dark:text-orange-300', badge: 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-500/20 dark:bg-orange-500/10 dark:text-orange-300', iconClass: 'bg-orange-100 text-orange-700 ring-orange-200 dark:bg-orange-500/10 dark:text-orange-300 dark:ring-orange-500/20' },
        pv: { icon: 'hard-drive', value: 'text-lime-700 dark:text-lime-300', badge: 'border-lime-200 bg-lime-50 text-lime-700 dark:border-lime-500/20 dark:bg-lime-500/10 dark:text-lime-300', iconClass: 'bg-lime-100 text-lime-700 ring-lime-200 dark:bg-lime-500/10 dark:text-lime-300 dark:ring-lime-500/20' },
    }

    const edgeColors = {
        owns: '#8b5cf6', scheduled_on: '#64748b', selects: '#10b981', routes_to: '#14b8a6',
        uses: '#0ea5e9', mounts: '#f97316', binds: '#65a30d', contains: '#94a3b8',
    }

    const relationshipUi = {
        owns: { icon: 'boxes', badge: typeUi.workload.badge },
        scheduled_on: { icon: 'server', badge: typeUi.node.badge },
        selects: { icon: 'network', badge: typeUi.service.badge },
        routes_to: { icon: 'route', badge: typeUi.ingress.badge },
        uses: { icon: 'link-2', badge: typeUi.configmap.badge },
        mounts: { icon: 'database', badge: typeUi.pvc.badge },
        binds: { icon: 'hard-drive', badge: typeUi.pv.badge },
        contains: { icon: 'folder-tree', badge: typeUi.namespace.badge },
    }

    const statusClasses = {
        healthy: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300',
        warning: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300',
        critical: 'border-red-200 bg-red-50 text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300',
        info: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300',
        unknown: 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-700 dark:text-slate-300',
    }

    const statusDotColors = { healthy: '#10b981', warning: '#f59e0b', critical: '#ef4444', info: '#3b82f6', unknown: '#94a3b8' }
    const statusDotCache = new Map()

    const escapeHtml = (value) => String(value ?? '')
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;').replaceAll("'", '&#039;')

    const humanizeType = (value) => ({
        cluster: 'Cluster', namespace: 'Namespace', node: 'Node', workload: 'Workload', pod: 'Pod',
        service: 'Service', ingress: 'Ingress', configmap: 'ConfigMap', secret: 'Secret', pvc: 'PVC', pv: 'PV',
    }[value] || value)

    const statusDotSvg = (tone) => {
        const normalized = statusDotColors[tone] ? tone : 'unknown'
        if (statusDotCache.has(normalized)) return statusDotCache.get(normalized)
        const color = statusDotColors[normalized]
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="${color}" stroke="white" stroke-width="2"/></svg>`
        const uri = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
        statusDotCache.set(normalized, uri)
        return uri
    }

    const formatDateTime = (value) => {
        if (!value) return 'Not reported'
        const parsed = new Date(value)
        if (Number.isNaN(parsed.getTime())) return value
        return new Intl.DateTimeFormat(undefined, {
            day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
        }).format(parsed)
    }

    const getTypeUi = (type) => typeUi[type] || typeUi.node
    const getTypeVisual = (type) => typeVisuals[type] || typeVisuals.node
    const getRelationshipUi = (relationship) => relationshipUi[relationship] || { icon: 'git-commit-horizontal', badge: typeUi.node.badge }

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

    const graphStyle = () => {
        const darkMode = document.documentElement.classList.contains('dark')
        const labelBackground = darkMode ? '#0f172a' : '#ffffff'
        return [
            {
                selector: 'node',
                style: {
                    'background-color': (node) => getTypeVisual(node.data('type')).fill,
                    'border-color': (node) => getTypeVisual(node.data('type')).border,
                    'border-width': 1.5,
                    'color': (node) => getTypeVisual(node.data('type')).text,
                    'font-family': 'Inter, sans-serif',
                    'font-size': 9,
                    'font-weight': 600,
                    'height': 36,
                    'label': workspaceState.nodeLabels ? 'data(display_label)' : '',
                    'min-zoomed-font-size': 7,
                    'overlay-opacity': 0,
                    'padding': 10,
                    'shape': 'round-rectangle',
                    'shadow-blur': 8,
                    'shadow-color': '#0f172a',
                    'shadow-offset-x': 0,
                    'shadow-offset-y': 2,
                    'shadow-opacity': 0.12,
                    'text-halign': 'center',
                    'text-margin-y': 0,
                    'text-max-width': 2000,
                    'text-valign': 'center',
                    'text-wrap': 'none',
                    'width': 'label',
                    'background-image': (node) => statusDotSvg(node.data('status_tone')),
                    'background-width': 14,
                    'background-height': 14,
                    'background-position-x': '96%',
                    'background-position-y': '10%',
                    'background-repeat': 'no-repeat',
                    'background-fit': 'none',
                    'background-image-containment': 'inside',
                },
            },
            { selector: 'node[type = "cluster"]', style: { 'font-size': 10, 'font-weight': 700, 'height': 42, 'padding': 14 } },
            { selector: 'node[type = "namespace"], node[type = "node"], node[type = "workload"]', style: { 'height': 38, 'padding': 12 } },
            { selector: 'node[type = "pod"], node[type = "configmap"], node[type = "secret"], node[type = "pvc"], node[type = "pv"]', style: { 'height': 34, 'padding': 10 } },
            {
                selector: 'edge',
                style: {
                    'curve-style': 'bezier',
                    'font-family': 'Inter, sans-serif',
                    'font-size': 8,
                    'label': '',
                    'line-color': (edge) => edgeColors[edge.data('relationship')] || '#cbd5e1',
                    'line-opacity': 0.55,
                    'min-zoomed-font-size': 7,
                    'overlay-opacity': 0,
                    'target-arrow-color': (edge) => edgeColors[edge.data('relationship')] || '#cbd5e1',
                    'target-arrow-shape': 'triangle',
                    'arrow-scale': 0.72,
                    'text-background-color': labelBackground,
                    'text-background-opacity': 0.92,
                    'text-background-padding': 2,
                    'text-rotation': 'autorotate',
                    'width': 1.35,
                },
            },
            { selector: 'edge.edge-label-visible', style: { 'label': 'data(label)' } },
            { selector: '.dimmed', style: { 'opacity': 0.10, 'text-opacity': 0.06 } },
            { selector: '.focused', style: { 'opacity': 1, 'text-opacity': 1, 'z-index': 999 } },
            { selector: '.path-active', style: { 'opacity': 1, 'text-opacity': 1, 'z-index': 1100, 'line-opacity': 1, 'width': 3, 'label': 'data(label)' } },
            { selector: 'node.path-active', style: { 'border-width': 3, 'shadow-opacity': 0.24 } },
            { selector: '.search-match', style: { 'border-color': '#eab308', 'border-width': 3, 'opacity': 1, 'z-index': 1150 } },
            { selector: ':selected', style: { 'border-color': '#1d4ed8', 'border-width': 3, 'line-color': '#1d4ed8', 'target-arrow-color': '#1d4ed8', 'z-index': 1200 } },
        ]
    }

    const getLayoutMode = () => layoutModeSelect?.value === 'dependency' ? 'dependency' : 'hierarchy'

    const layoutOptions = () => {
        if (getLayoutMode() === 'dependency') {
            return {
                name: 'cose', animate: 'end', animationDuration: 420, animationEasing: 'ease-out-cubic', fit: true,
                nodeDimensionsIncludeLabels: true, padding: 72, idealEdgeLength: 175, edgeElasticity: 100,
                nodeRepulsion: 620000, gravity: 0.30, numIter: 1600, componentSpacing: 135,
                nestingFactor: 0.8, initialTemp: 200, coolingFactor: 0.96, minTemp: 1, randomize: true,
            }
        }
        return {
            name: 'breadthfirst', animate: false, circle: false, directed: true, fit: true, grid: true,
            maximal: false, nodeDimensionsIncludeLabels: true, padding: 52, spacingFactor: 1.62,
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
        canvasShell.style.height = '780px'
        canvasShell.style.minHeight = '780px'
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
            runtimeStatus.innerHTML = ''
            return
        }
        runtimeStatus.classList.remove('hidden')
        runtimeStatus.innerHTML = `<span class="inline-flex items-center gap-2"><span class="h-2 w-2 rounded-full bg-blue-500"></span>${escapeHtml(message)}</span>`
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
        namespaceSelect.innerHTML = '<option value="">All Namespaces</option>'
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

    const updateUrl = () => {
        const url = new URL(window.location.href)
        const values = {
            cluster_id: clusterSelect.value,
            namespace: namespaceSelect.disabled ? '' : namespaceSelect.value,
            scope: scopeSelect.value,
            depth: depthSelect.value,
            layout: getLayoutMode(),
        }
        Object.entries(values).forEach(([key, value]) => {
            const isDefault = (key === 'scope' && value === 'all') || (key === 'depth' && value === '1') || (key === 'layout' && value === 'hierarchy')
            if (value && !isDefault) url.searchParams.set(key, value)
            else url.searchParams.delete(key)
        })
        window.history.replaceState({}, '', url)
    }

    const applyStateToControls = () => {
        if (nodeLabelToggle) nodeLabelToggle.checked = workspaceState.nodeLabels
        if (edgeLabelToggle) edgeLabelToggle.checked = workspaceState.edgeLabels
        if (groupNamespaceToggle) groupNamespaceToggle.checked = workspaceState.groupByNamespace
        resourceToggles.forEach((toggle) => { toggle.checked = workspaceState.resources[toggle.dataset.topologyResourceToggle] !== false })
        relationshipToggles.forEach((toggle) => { toggle.checked = workspaceState.relationships[toggle.dataset.topologyRelationshipToggle] !== false })
    }

    const updateSummary = (payload) => {
        const summary = payload.summary || {}
        const setText = (id, value) => { const element = $(id); if (element) element.textContent = value }
        setText('topology-hero-clusters', summary.clusters ?? 0)
        setText('topology-hero-namespaces', summary.namespaces ?? 0)
        setText('topology-hero-resources', summary.resources ?? 0)
        setText('topology-hero-relationships', summary.relationships ?? 0)
        setText('topology-hero-collected', summary.last_collected_at ? formatDateTime(summary.last_collected_at) : 'No snapshot')
        if (filterSummary) filterSummary.textContent = `${summary.scope_label || 'All Resources'} · ${summary.depth_label || '1 Level'}`
        document.querySelectorAll('[data-topology-count-type]').forEach((element) => {
            element.textContent = payload.type_counts?.[element.dataset.topologyCountType] ?? 0
        })
        if (summary.truncated) {
            limitWarning?.classList.remove('hidden')
            if (limitMessage) limitMessage.textContent = `${summary.omitted_nodes || 0} resources were omitted. Narrow the cluster or namespace scope to display them.`
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
                node.data('display_label', `${base}  +${count}`)
            } else {
                node.data('display_label', base)
            }
        })
    }

    const enabledResourceTypes = () => new Set(resourceToggles.filter((toggle) => toggle.checked).map((toggle) => toggle.dataset.topologyResourceToggle))
    const enabledRelationshipTypes = () => new Set(relationshipToggles.filter((toggle) => toggle.checked).map((toggle) => toggle.dataset.topologyRelationshipToggle))

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
        if (!cy) return
        recomputeCollapsedHidden()
        const resources = enabledResourceTypes()
        const relationships = enabledRelationshipTypes()
        cy.nodes().forEach((node) => {
            const visible = resources.has(node.data('type')) && !collapsedHiddenIds.has(node.id())
            node.style('display', visible ? 'element' : 'none')
        })
        cy.edges().forEach((edge) => {
            const endpointsVisible = edge.source().style('display') !== 'none' && edge.target().style('display') !== 'none'
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
        const add = (collection) => collection.forEach((item) => { if (item.id() !== node.id() && !anchors.some((existing) => existing.id() === item.id())) anchors.push(item) })
        add(sameCluster.filter('[type = "cluster"]'))
        if (data.namespace) add(sameCluster.filter((candidate) => candidate.data('type') === 'namespace' && candidate.data('namespace') === data.namespace))
        add(node.connectedEdges(':visible').connectedNodes(':visible').filter('[type = "workload"], [type = "node"], [type = "service"], [type = "ingress"]'))
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

    const emptyDetailHtml = () => `
        <div class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center dark:border-slate-600 dark:bg-slate-900/40">
            <i data-lucide="mouse-pointer-click" class="mx-auto h-7 w-7 text-slate-400"></i>
            <p class="mt-3 text-sm font-medium text-slate-700 dark:text-slate-200">Nothing selected</p>
            <p class="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">Select a resource or relationship to inspect its inventory context.</p>
        </div>`

    const renderValueRows = (fields, type) => {
        const ui = getTypeUi(type)
        return fields.map((field) => `
            <div class="flex items-start justify-between gap-3 border-b border-slate-100 py-2.5 last:border-b-0 dark:border-slate-700/70">
                <dt class="text-xs font-normal text-slate-500 dark:text-slate-400">${escapeHtml(field.label)}</dt>
                <dd class="max-w-[12rem] break-words text-right text-xs font-normal ${ui.value}">${escapeHtml(field.value)}</dd>
            </div>`).join('')
    }

    const renderRelationshipRows = (node) => {
        const edges = node.connectedEdges(':visible')
        if (!edges.length) {
            return `<div class="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-xs text-slate-500 dark:border-slate-600 dark:bg-slate-900/40 dark:text-slate-400">No visible relationships.</div>`
        }
        return edges.map((edge) => {
            const sourceSelected = edge.source().id() === node.id()
            const peer = sourceSelected ? edge.target() : edge.source()
            const edgeData = edge.data()
            const ui = getRelationshipUi(edgeData.relationship)
            return `
                <button type="button" data-topology-related-node="${escapeHtml(peer.id())}" class="flex w-full items-start gap-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-left transition hover:border-blue-200 hover:bg-blue-50/50 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-blue-500/30 dark:hover:bg-blue-500/10">
                    <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border ${ui.badge}"><i data-lucide="${ui.icon}" class="h-4 w-4"></i></span>
                    <span class="min-w-0 flex-1">
                        <span class="flex flex-wrap items-center gap-2"><span class="text-[10px] font-medium uppercase tracking-wide text-slate-400">${sourceSelected ? 'Outbound' : 'Inbound'}</span><span class="rounded-full border px-2 py-0.5 text-[9px] font-medium ${ui.badge}">${escapeHtml(edgeData.label || edgeData.relationship)}</span></span>
                        <span class="mt-1 block break-words text-xs font-medium text-slate-900 dark:text-white">${escapeHtml(peer.data('label') || peer.id())}</span>
                        <span class="mt-1 block text-[10px] text-slate-500 dark:text-slate-400">${escapeHtml(humanizeType(peer.data('type')))}</span>
                    </span>
                    <i data-lucide="chevron-right" class="mt-2 h-3.5 w-3.5 shrink-0 text-slate-400"></i>
                </button>`
        }).join('')
    }

    const renderNodeDetails = (node, initialTab = activeDrawerTab) => {
        if (!node?.length) return
        selectedNodeId = node.id()
        activeDrawerTab = initialTab === 'relationships' ? 'relationships' : 'details'
        const data = node.data()
        const ui = getTypeUi(data.type)
        const statusClass = statusClasses[data.status_tone] || statusClasses.unknown
        const childCount = descendantsOf(node.id()).size
        const isCollapsed = collapsedNodeIds.has(node.id())
        const connectedCount = node.connectedEdges(':visible').length
        const fields = Array.isArray(data.fields) ? data.fields : []

        const detailsHtml = `
            <div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
                <div class="flex items-center justify-between gap-3"><h5 class="text-xs font-semibold text-slate-900 dark:text-white">Resource context</h5><span class="rounded-full border px-2.5 py-1 text-[10px] font-medium ${ui.badge}">${connectedCount} relationships</span></div>
                <dl class="mt-3">
                    <div class="flex items-start justify-between gap-3 border-b border-slate-100 py-2.5 dark:border-slate-700/70"><dt class="text-xs text-slate-500 dark:text-slate-400">Cluster</dt><dd class="max-w-[12rem] break-words text-right text-xs ${ui.value}">${escapeHtml(data.cluster_name || 'Not reported')}</dd></div>
                    ${data.namespace ? `<div class="flex items-start justify-between gap-3 border-b border-slate-100 py-2.5 dark:border-slate-700/70"><dt class="text-xs text-slate-500 dark:text-slate-400">Namespace</dt><dd class="max-w-[12rem] break-words text-right text-xs ${ui.value}">${escapeHtml(data.namespace)}</dd></div>` : ''}
                    ${renderValueRows(fields, data.type)}
                    <div class="flex items-start justify-between gap-3 py-2.5"><dt class="text-xs text-slate-500 dark:text-slate-400">Collected</dt><dd class="max-w-[12rem] break-words text-right text-xs ${ui.value}">${escapeHtml(formatDateTime(data.collected_at))}</dd></div>
                </dl>
            </div>
            ${data.action_url ? `<a href="${escapeHtml(data.action_url)}" class="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700">Open ${escapeHtml(humanizeType(data.type))} Inventory<i data-lucide="arrow-up-right" class="h-4 w-4"></i></a>` : ''}`

        detailContent.innerHTML = `
            <div class="space-y-4">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
                    <div class="flex items-start gap-3">
                        <span class="mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ring-1 ${ui.iconClass}"><i data-lucide="${ui.icon}" class="h-5 w-5"></i></span>
                        <div class="min-w-0 flex-1"><h4 class="break-words text-sm font-semibold text-slate-950 dark:text-white">${escapeHtml(data.label)}</h4><p class="mt-1 text-xs text-slate-500 dark:text-slate-400">${escapeHtml(data.kind || humanizeType(data.type))}</p><div class="mt-2 flex flex-wrap gap-2"><span class="rounded-full border px-2.5 py-1 text-[10px] font-medium ${ui.badge}">${escapeHtml(humanizeType(data.type))}</span><span class="rounded-full border px-2.5 py-1 text-[10px] font-medium ${statusClass}">${escapeHtml(data.status || 'Unknown')}</span></div></div>
                    </div>
                    ${data.description ? `<p class="mt-3 text-xs leading-5 text-slate-600 dark:text-slate-300">${escapeHtml(data.description)}</p>` : ''}
                </div>

                <div class="grid grid-cols-2 gap-2">
                    <button type="button" id="topology-highlight-path-button" class="inline-flex items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-medium text-blue-700 transition hover:bg-blue-100 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300 dark:hover:bg-blue-500/20"><i data-lucide="route" class="h-3.5 w-3.5"></i>${pathHighlightActive ? 'Clear path' : 'Highlight path'}</button>
                    <button type="button" id="topology-collapse-button" ${childCount ? '' : 'disabled'} class="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"><i data-lucide="${isCollapsed ? 'unfold-vertical' : 'fold-vertical'}" class="h-3.5 w-3.5"></i>${childCount ? (isCollapsed ? `Expand ${childCount}` : `Collapse ${childCount}`) : 'No loaded children'}</button>
                </div>

                <div class="grid grid-cols-2 rounded-xl border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-900/60">
                    <button type="button" data-topology-node-tab="details" class="rounded-lg px-3 py-2 text-xs font-medium">Details</button>
                    <button type="button" data-topology-node-tab="relationships" class="rounded-lg px-3 py-2 text-xs font-medium">Relationships <span class="ml-1 text-[10px] opacity-70">${connectedCount}</span></button>
                </div>
                <div id="topology-node-tab-panel"></div>
            </div>`

        const panel = detailContent.querySelector('#topology-node-tab-panel')
        const tabButtons = Array.from(detailContent.querySelectorAll('[data-topology-node-tab]'))
        const activateTab = (tab) => {
            activeDrawerTab = tab === 'relationships' ? 'relationships' : 'details'
            panel.innerHTML = activeDrawerTab === 'relationships' ? `<div class="space-y-2">${renderRelationshipRows(node)}</div>` : detailsHtml
            tabButtons.forEach((button) => {
                const active = button.dataset.topologyNodeTab === activeDrawerTab
                button.className = active
                    ? 'rounded-lg bg-white px-3 py-2 text-xs font-semibold text-blue-700 shadow-sm dark:bg-slate-800 dark:text-blue-300'
                    : 'rounded-lg px-3 py-2 text-xs font-medium text-slate-500 transition hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            })
            panel.querySelectorAll('[data-topology-related-node]').forEach((button) => button.addEventListener('click', () => selectNodeById(button.dataset.topologyRelatedNode, 'relationships')))
            window.lucide?.createIcons()
        }
        tabButtons.forEach((button) => button.addEventListener('click', () => activateTab(button.dataset.topologyNodeTab)))
        detailContent.querySelector('#topology-highlight-path-button')?.addEventListener('click', () => {
            if (pathHighlightActive) {
                clearPathHighlight()
                renderNodeDetails(node, activeDrawerTab)
            } else highlightPaths(node)
        })
        detailContent.querySelector('#topology-collapse-button')?.addEventListener('click', () => {
            if (!childCount) return
            if (isCollapsed) collapsedNodeIds.delete(node.id())
            else collapsedNodeIds.add(node.id())
            applyVisibility({ relayout: true })
            const refreshed = cy.getElementById(node.id())
            if (refreshed?.length) renderNodeDetails(refreshed, activeDrawerTab)
        })
        activateTab(activeDrawerTab)
        window.lucide?.createIcons()
    }

    const renderEdgeDetails = (edge) => {
        selectedNodeId = null
        pathHighlightActive = false
        const data = edge.data()
        const ui = getRelationshipUi(data.relationship)
        const color = edgeColors[data.relationship] || '#64748b'
        detailContent.innerHTML = `
            <div class="space-y-4">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
                    <div class="flex items-start gap-3"><span class="flex h-11 w-11 items-center justify-center rounded-2xl border ${ui.badge}"><i data-lucide="${ui.icon}" class="h-5 w-5"></i></span><div class="min-w-0 flex-1"><h4 class="break-words text-sm font-semibold text-slate-950 dark:text-white">${escapeHtml(data.label || 'Relationship')}</h4><p class="mt-1 text-xs text-slate-500 dark:text-slate-400">Topology relationship</p><span class="mt-2 inline-flex rounded-full border px-2.5 py-1 text-[10px] font-medium ${ui.badge}">${escapeHtml(data.relationship)}</span></div></div>
                    ${data.description ? `<p class="mt-3 text-xs leading-5 text-slate-600 dark:text-slate-300">${escapeHtml(data.description)}</p>` : ''}
                </div>
                <div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800"><div class="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-900/40"><span class="h-3 w-3 rounded-full" style="background:${color}"></span><div class="min-w-0 flex-1 space-y-1"><p class="break-words text-xs font-medium text-slate-900 dark:text-white">${escapeHtml(data.source_label)}</p><p class="text-[10px] uppercase tracking-wide text-slate-400">${escapeHtml(data.label)}</p><p class="break-words text-xs font-medium text-slate-900 dark:text-white">${escapeHtml(data.target_label)}</p></div></div></div>
            </div>`
        window.lucide?.createIcons()
    }

    const clearSelection = () => {
        if (!cy) return
        selectedNodeId = null
        pathHighlightActive = false
        cy.elements().removeClass('dimmed focused path-active edge-label-visible search-match')
        cy.elements().unselect()
        updateEdgeLabelClasses()
        detailContent.innerHTML = emptyDetailHtml()
        window.lucide?.createIcons()
    }

    const selectNodeById = (id, tab = 'details') => {
        if (!cy) return
        const node = cy.getElementById(id)
        if (!node?.length || !node.visible()) return
        focusNeighborhood(node)
        renderNodeDetails(node, tab)
        cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 1.05) }, { duration: 220 })
        hideSearchResults()
    }

    const attachGraphEvents = () => {
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
        cy.on('tap', (event) => { if (event.target === cy) clearSelection() })
        cy.on('mouseover', 'edge', (event) => event.target.addClass('edge-label-visible'))
        cy.on('mouseout', 'edge', (event) => { if (!workspaceState.edgeLabels && !event.target.selected() && !event.target.hasClass('path-active')) event.target.removeClass('edge-label-visible') })
        cy.on('mouseover', 'node', (event) => { if (!workspaceState.edgeLabels) event.target.connectedEdges(':visible').addClass('edge-label-visible') })
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

    const renderSearchResults = (term) => {
        if (!cy || !searchResults) return
        const normalized = term.trim().toLowerCase()
        cy.nodes().removeClass('search-match')
        if (normalized.length < 2) {
            hideSearchResults()
            if (searchSummary) searchSummary.textContent = 'Search and open a resource directly in the graph.'
            return
        }
        const matches = cy.nodes(':visible').filter((node) => {
            const data = node.data()
            return [data.label, data.kind, data.type, data.cluster_name, data.namespace, data.status]
                .filter(Boolean).join(' ').toLowerCase().includes(normalized)
        }).sort((a, b) => {
            const aLabel = String(a.data('label') || '').toLowerCase()
            const bLabel = String(b.data('label') || '').toLowerCase()
            return Number(bLabel.startsWith(normalized)) - Number(aLabel.startsWith(normalized)) || aLabel.localeCompare(bLabel)
        })
        matches.addClass('search-match')
        const limited = matches.slice(0, 8)
        if (!limited.length) {
            searchResults.innerHTML = '<div class="px-3 py-3 text-xs text-slate-500 dark:text-slate-400">No matching resource in the current graph.</div>'
        } else {
            searchResults.innerHTML = limited.map((node) => {
                const data = node.data()
                const ui = getTypeUi(data.type)
                return `<button type="button" data-topology-search-node="${escapeHtml(node.id())}" class="flex w-full items-start gap-3 border-b border-slate-100 px-3 py-2.5 text-left last:border-b-0 hover:bg-blue-50 dark:border-slate-700 dark:hover:bg-blue-500/10"><span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ring-1 ${ui.iconClass}"><i data-lucide="${ui.icon}" class="h-4 w-4"></i></span><span class="min-w-0 flex-1"><span class="block truncate text-xs font-medium text-slate-900 dark:text-white">${escapeHtml(data.label)}</span><span class="mt-1 block truncate text-[10px] text-slate-500 dark:text-slate-400">${escapeHtml(humanizeType(data.type))}${data.namespace ? ` · ${escapeHtml(data.namespace)}` : ''} · ${escapeHtml(data.cluster_name || 'Unknown cluster')}</span></span></button>`
            }).join('')
        }
        searchResults.classList.remove('hidden')
        searchResults.querySelectorAll('[data-topology-search-node]').forEach((button) => button.addEventListener('click', () => selectNodeById(button.dataset.topologySearchNode)))
        if (searchSummary) searchSummary.textContent = `${matches.length} matching ${matches.length === 1 ? 'resource' : 'resources'} found.`
        window.lucide?.createIcons()
    }

    const hideSearchResults = () => searchResults?.classList.add('hidden')

    const scheduleBoundaryUpdate = () => {
        if (boundaryFrame) cancelAnimationFrame(boundaryFrame)
        boundaryFrame = requestAnimationFrame(updateNamespaceBoundaries)
    }

    const updateNamespaceBoundaries = () => {
        boundaryFrame = null
        if (!boundaryLayer) return
        boundaryLayer.innerHTML = ''
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
            boundary.className = 'absolute rounded-2xl border border-dashed border-indigo-300 bg-indigo-50/25 dark:border-indigo-500/30 dark:bg-indigo-500/5'
            boundary.style.left = `${box.x1 - padding}px`
            boundary.style.top = `${box.y1 - padding}px`
            boundary.style.width = `${box.w + padding * 2}px`
            boundary.style.height = `${box.h + padding * 2}px`
            boundary.innerHTML = `<span class="absolute -top-3 left-3 rounded-full border border-indigo-200 bg-white px-2 py-0.5 text-[9px] font-medium text-indigo-700 shadow-sm dark:border-indigo-500/30 dark:bg-slate-900 dark:text-indigo-300">${escapeHtml(namespace)}</span>`
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
        if (!cy) return
        const payload = {
            product: 'KAORI',
            generated_at: new Date().toISOString(),
            filters: { cluster_id: clusterSelect.value, namespace: namespaceSelect.value, scope: scopeSelect.value, depth: depthSelect.value, layout: getLayoutMode() },
            summary: currentPayload.summary || {},
            nodes: cy.nodes(':visible').map((node) => node.data()),
            edges: cy.edges(':visible').map((edge) => edge.data()),
        }
        downloadBlob(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }), `kaori-topology-${Date.now()}.json`)
    }

    const exportPng = () => {
        if (!cy) return
        const dataUrl = cy.png({ full: true, scale: 2, bg: '#ffffff' })
        const image = new Image()
        image.onload = () => {
            const footer = 42
            const output = document.createElement('canvas')
            output.width = image.width
            output.height = image.height + footer
            const ctx = output.getContext('2d')
            ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, output.width, output.height)
            ctx.drawImage(image, 0, 0)
            ctx.fillStyle = '#475569'; ctx.font = '24px sans-serif'
            const collected = currentPayload.summary?.last_collected_at ? formatDateTime(currentPayload.summary.last_collected_at) : 'No snapshot timestamp'
            ctx.fillText(`KAORI · Kubernetes Topology · ${collected}`, 18, image.height + 29)
            output.toBlob((blob) => { if (blob) downloadBlob(blob, `kaori-topology-${Date.now()}.png`) }, 'image/png')
        }
        image.src = dataUrl
    }

    const setLoading = (state) => {
        loading?.classList.toggle('hidden', !state)
        const refresh = $('topology-refresh-button')
        if (refresh) refresh.disabled = state
    }

    const createGraph = (payload) => {
        currentPayload = payload
        if (cy) cy.destroy()
        collapsedNodeIds = new Set()
        collapsedHiddenIds = new Set()
        selectedNodeId = null
        pathHighlightActive = false
        const prepared = prepareElements(payload)
        const hasNodes = prepared.nodes.length > 0
        emptyState?.classList.toggle('hidden', hasNodes)
        emptyState?.classList.toggle('flex', !hasNodes)
        updateSummary(payload)
        if (!hasNodes) {
            cy = null
            setRuntimeStatus()
            return
        }
        ensureCanvasDimensions()
        setRuntimeStatus(`Rendering ${prepared.nodes.length} resources and ${prepared.edges.length} relationships...`)
        try {
            cy = window.cytoscape({
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
                credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: fetchController.signal,
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

    if (!window.cytoscape) {
        setRuntimeStatus()
        showError('The local Cytoscape.js renderer could not be loaded.')
        return
    }

    applyStateToControls()
    syncLayoutFromUrl()
    updateNamespaceOptions(config.filters?.namespace || '')
    createGraph(currentPayload)

    clusterSelect.addEventListener('change', () => { updateNamespaceOptions(''); fetchGraph() })
    namespaceSelect.addEventListener('change', fetchGraph)
    scopeSelect.addEventListener('change', fetchGraph)
    depthSelect.addEventListener('change', fetchGraph)
    layoutModeSelect?.addEventListener('change', () => { updateUrl(); applyCurrentLayout() })

    nodeLabelToggle?.addEventListener('change', () => {
        workspaceState.nodeLabels = nodeLabelToggle.checked
        saveWorkspaceState()
        if (cy) cy.style().selector('node').style('label', workspaceState.nodeLabels ? 'data(display_label)' : '').update()
        scheduleBoundaryUpdate()
    })

    edgeLabelToggle?.addEventListener('change', () => {
        workspaceState.edgeLabels = edgeLabelToggle.checked
        saveWorkspaceState(); updateEdgeLabelClasses()
    })

    groupNamespaceToggle?.addEventListener('change', () => {
        workspaceState.groupByNamespace = groupNamespaceToggle.checked
        saveWorkspaceState(); scheduleBoundaryUpdate()
    })


    resourceToggles.forEach((toggle) => toggle.addEventListener('change', () => {
        workspaceState.resources[toggle.dataset.topologyResourceToggle] = toggle.checked
        saveWorkspaceState(); applyVisibility({ relayout: true })
    }))

    relationshipToggles.forEach((toggle) => toggle.addEventListener('change', () => {
        workspaceState.relationships[toggle.dataset.topologyRelationshipToggle] = toggle.checked
        saveWorkspaceState(); applyVisibility({ relayout: getLayoutMode() === 'dependency' })
    }))

    searchInput.addEventListener('input', () => {
        window.clearTimeout(searchTimer)
        searchTimer = window.setTimeout(() => renderSearchResults(searchInput.value), 160)
    })
    searchInput.addEventListener('focus', () => renderSearchResults(searchInput.value))
    document.addEventListener('click', (event) => {
        if (!searchResults?.contains(event.target) && event.target !== searchInput) hideSearchResults()
    })

    $('topology-fit-button')?.addEventListener('click', fitGraphToCanvas)
    $('topology-reset-button')?.addEventListener('click', () => {
        searchInput.value = ''
        hideSearchResults()
        collapsedNodeIds = new Set()
        clearSelection()
        applyVisibility({ relayout: true })
        if (searchSummary) searchSummary.textContent = 'Search and open a resource directly in the graph.'
    })
    $('topology-refresh-button')?.addEventListener('click', fetchGraph)
    $('topology-export-png-button')?.addEventListener('click', exportPng)
    $('topology-export-json-button')?.addEventListener('click', exportJson)

    if (window.ResizeObserver && canvasShell) {
        const observer = new ResizeObserver(() => {
            if (!cy) return
            cy.resize(); scheduleBoundaryUpdate()
        })
        observer.observe(canvasShell)
    }

    $('theme-toggle')?.addEventListener('click', () => window.setTimeout(() => {
        if (!cy) return
        cy.style(graphStyle())
        scheduleBoundaryUpdate()
    }, 0))
})()
