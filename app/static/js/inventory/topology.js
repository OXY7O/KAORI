(() => {
    const config = window.KAORI_TOPOLOGY

    if (!config) {
        return
    }

    const canvas = document.getElementById('topology-canvas')
    const clusterSelect = document.getElementById('topology-cluster')
    const namespaceSelect = document.getElementById('topology-namespace')
    const scopeSelect = document.getElementById('topology-scope')
    const depthSelect = document.getElementById('topology-depth')
    const searchInput = document.getElementById('topology-search')
    const loading = document.getElementById('topology-loading')
    const errorPanel = document.getElementById('topology-error')
    const runtimeStatus = document.getElementById('topology-runtime-status')
    const emptyState = document.getElementById('topology-empty-state')
    const limitWarning = document.getElementById('topology-limit-warning')
    const limitMessage = document.getElementById('topology-limit-message')
    const detailContent = document.getElementById('topology-detail-content')
    const nodeLabelToggle = document.getElementById('topology-node-label-toggle')
    const edgeLabelToggle = document.getElementById('topology-edge-label-toggle')
    const layoutModeSelect = document.getElementById('topology-layout-mode')
    const relationshipToggles = Array.from(document.querySelectorAll('[data-topology-relationship-toggle]'))
    const searchSummary = document.getElementById('topology-search-summary')
    const filterSummary = document.getElementById('topology-filter-summary')

    let cy = null
    let currentPayload = config.initial_graph || { nodes: [], edges: [], summary: {}, type_counts: {} }
    let fetchController = null
    let searchTimer = null
    let selectedNodeId = null

    const typeColors = {
        cluster: '#2563eb',
        namespace: '#6366f1',
        node: '#64748b',
        workload: '#8b5cf6',
        pod: '#06b6d4',
        service: '#10b981',
        ingress: '#14b8a6',
        configmap: '#0ea5e9',
        secret: '#f59e0b',
        pvc: '#f97316',
        pv: '#65a30d',
    }

    const edgeColors = {
        owns: '#8b5cf6',
        scheduled_on: '#64748b',
        selects: '#10b981',
        routes_to: '#14b8a6',
        uses: '#0ea5e9',
        mounts: '#f97316',
        binds: '#65a30d',
        contains: '#94a3b8',
    }


    const typeVisuals = {
        cluster: { fill: '#dbeafe', border: '#3b82f6' },
        namespace: { fill: '#e0e7ff', border: '#6366f1' },
        node: { fill: '#e2e8f0', border: '#64748b' },
        workload: { fill: '#ede9fe', border: '#8b5cf6' },
        pod: { fill: '#cffafe', border: '#06b6d4' },
        service: { fill: '#d1fae5', border: '#10b981' },
        ingress: { fill: '#ccfbf1', border: '#14b8a6' },
        configmap: { fill: '#e0f2fe', border: '#0ea5e9' },
        secret: { fill: '#fef3c7', border: '#f59e0b' },
        pvc: { fill: '#ffedd5', border: '#f97316' },
        pv: { fill: '#ecfccb', border: '#65a30d' },
    }

    const typeLegendIcons = {
        cluster: 'server-cog',
        namespace: 'layers-3',
        node: 'server',
        workload: 'boxes',
        pod: 'circle-dot',
        service: 'network',
        ingress: 'route',
        configmap: 'file-cog',
        secret: 'key-round',
        pvc: 'database',
        pv: 'hard-drive',
    }

    const getTypeVisual = (type) => typeVisuals[type] || typeVisuals.node


    const typeUi = {
        cluster: {
            icon: 'server-cog',
            iconClasses: 'bg-blue-100 text-blue-700 ring-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20',
            valueClasses: 'text-blue-700 dark:text-blue-300',
            softBadgeClasses: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300',
        },
        namespace: {
            icon: 'layers-3',
            iconClasses: 'bg-indigo-100 text-indigo-700 ring-indigo-200 dark:bg-indigo-500/10 dark:text-indigo-300 dark:ring-indigo-500/20',
            valueClasses: 'text-indigo-700 dark:text-indigo-300',
            softBadgeClasses: 'border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-500/20 dark:bg-indigo-500/10 dark:text-indigo-300',
        },
        node: {
            icon: 'server',
            iconClasses: 'bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-700/60 dark:text-slate-300 dark:ring-slate-600',
            valueClasses: 'text-slate-700 dark:text-slate-300',
            softBadgeClasses: 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-600 dark:bg-slate-700/40 dark:text-slate-300',
        },
        workload: {
            icon: 'boxes',
            iconClasses: 'bg-violet-100 text-violet-700 ring-violet-200 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/20',
            valueClasses: 'text-violet-700 dark:text-violet-300',
            softBadgeClasses: 'border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/20 dark:bg-violet-500/10 dark:text-violet-300',
        },
        pod: {
            icon: 'circle-dot',
            iconClasses: 'bg-cyan-100 text-cyan-700 ring-cyan-200 dark:bg-cyan-500/10 dark:text-cyan-300 dark:ring-cyan-500/20',
            valueClasses: 'text-cyan-700 dark:text-cyan-300',
            softBadgeClasses: 'border-cyan-200 bg-cyan-50 text-cyan-700 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-300',
        },
        service: {
            icon: 'network',
            iconClasses: 'bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20',
            valueClasses: 'text-emerald-700 dark:text-emerald-300',
            softBadgeClasses: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300',
        },
        ingress: {
            icon: 'route',
            iconClasses: 'bg-teal-100 text-teal-700 ring-teal-200 dark:bg-teal-500/10 dark:text-teal-300 dark:ring-teal-500/20',
            valueClasses: 'text-teal-700 dark:text-teal-300',
            softBadgeClasses: 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-500/20 dark:bg-teal-500/10 dark:text-teal-300',
        },
        configmap: {
            icon: 'file-cog',
            iconClasses: 'bg-sky-100 text-sky-700 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/20',
            valueClasses: 'text-sky-700 dark:text-sky-300',
            softBadgeClasses: 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300',
        },
        secret: {
            icon: 'key-round',
            iconClasses: 'bg-amber-100 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20',
            valueClasses: 'text-amber-700 dark:text-amber-300',
            softBadgeClasses: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300',
        },
        pvc: {
            icon: 'database',
            iconClasses: 'bg-orange-100 text-orange-700 ring-orange-200 dark:bg-orange-500/10 dark:text-orange-300 dark:ring-orange-500/20',
            valueClasses: 'text-orange-700 dark:text-orange-300',
            softBadgeClasses: 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-500/20 dark:bg-orange-500/10 dark:text-orange-300',
        },
        pv: {
            icon: 'hard-drive',
            iconClasses: 'bg-lime-100 text-lime-700 ring-lime-200 dark:bg-lime-500/10 dark:text-lime-300 dark:ring-lime-500/20',
            valueClasses: 'text-lime-700 dark:text-lime-300',
            softBadgeClasses: 'border-lime-200 bg-lime-50 text-lime-700 dark:border-lime-500/20 dark:bg-lime-500/10 dark:text-lime-300',
        },
    }

    const relationshipUi = {
        owns: { icon: 'boxes', badgeClasses: typeUi.workload.softBadgeClasses },
        scheduled_on: { icon: 'server', badgeClasses: typeUi.node.softBadgeClasses },
        selects: { icon: 'network', badgeClasses: typeUi.service.softBadgeClasses },
        routes_to: { icon: 'route', badgeClasses: typeUi.ingress.softBadgeClasses },
        uses: { icon: 'link-2', badgeClasses: typeUi.configmap.softBadgeClasses },
        mounts: { icon: 'database', badgeClasses: typeUi.pvc.softBadgeClasses },
        binds: { icon: 'hard-drive', badgeClasses: typeUi.pv.softBadgeClasses },
        contains: { icon: 'folder-tree', badgeClasses: typeUi.namespace.softBadgeClasses },
    }

    const getTypeUi = (type) => typeUi[type] || typeUi.node
    const getRelationshipUi = (rel) => relationshipUi[rel] || { icon: 'git-commit-horizontal', badgeClasses: typeUi.node.softBadgeClasses }

    const statusClasses = {
        healthy: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300',
        warning: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300',
        critical: 'border-red-200 bg-red-50 text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300',
        info: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300',
        unknown: 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-700 dark:text-slate-300',
    }

    const escapeHtml = (value) => String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;')

    const humanizeType = (value) => {
        const labels = {
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
        }
        return labels[value] || value
    }

    const formatNodeLabel = (value) => {
        const label = String(value || '').trim()
        const maxLength = 28
        return label.length > maxLength
            ? `${label.slice(0, maxLength - 1).trimEnd()}…`
            : label
    }

    const formatDateTime = (value) => {
        if (!value) {
            return 'Not reported'
        }

        const parsed = new Date(value)
        if (Number.isNaN(parsed.getTime())) {
            return value
        }

        return new Intl.DateTimeFormat(undefined, {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZoneName: 'short',
        }).format(parsed)
    }

    const graphStyle = () => {
        const darkMode = document.documentElement.classList.contains('dark')
        const labelBackground = darkMode ? '#0f172a' : '#ffffff'
        const labelColor = darkMode ? '#e2e8f0' : '#0f172a'

        return [
        {
            selector: 'node',
            style: {
                'background-color': (node) => getTypeVisual(node.data('type')).fill,
                'border-color': (node) => getTypeVisual(node.data('type')).border,
                'border-width': 2.2,
                'color': labelColor,
                'font-family': 'Inter, sans-serif',
                'font-size': 10,
                'font-weight': 600,
                'height': 44,
                'label': nodeLabelToggle && nodeLabelToggle.checked ? 'data(display_label)' : '',
                'min-zoomed-font-size': 8,
                'overlay-opacity': 0,
                'shape': 'round-rectangle',
                'shadow-blur': 10,
                'shadow-color': darkMode ? '#020617' : '#94a3b8',
                'shadow-opacity': darkMode ? 0.18 : 0.16,
                'shadow-offset-x': 0,
                'shadow-offset-y': 3,
                'text-background-color': labelBackground,
                'text-background-opacity': 0.92,
                'text-background-padding': 3,
                'text-halign': 'center',
                'text-margin-y': 10,
                'text-max-width': 190,
                'text-valign': 'bottom',
                'text-wrap': 'none',
                'width': 62,
            },
        },
        {
            selector: 'node[type = "cluster"]',
            style: {
                'shape': 'round-rectangle',
                'height': 48,
                'width': 76,
            },
        },
        {
            selector: 'node[type = "namespace"]',
            style: {
                'shape': 'round-rectangle',
                'height': 44,
                'width': 68,
            },
        },
        {
            selector: 'node[type = "node"]',
            style: {
                'shape': 'round-rectangle',
                'height': 44,
                'width': 68,
            },
        },
        {
            selector: 'node[type = "workload"]',
            style: {
                'shape': 'round-rectangle',
                'height': 44,
                'width': 66,
            },
        },
        {
            selector: 'node[type = "pod"]',
            style: {
                'shape': 'ellipse',
                'height': 50,
                'width': 50,
            },
        },
        {
            selector: 'node[type = "service"]',
            style: {
                'shape': 'round-rectangle',
                'height': 44,
                'width': 64,
            },
        },
        {
            selector: 'node[type = "ingress"]',
            style: {
                'shape': 'round-rectangle',
                'height': 44,
                'width': 64,
            },
        },
        {
            selector: 'node[type = "configmap"], node[type = "secret"]',
            style: {
                'shape': 'round-rectangle',
                'height': 42,
                'width': 62,
            },
        },
        {
            selector: 'node[type = "pvc"], node[type = "pv"]',
            style: {
                'shape': 'round-rectangle',
                'height': 42,
                'width': 62,
            },
        },
        {
            selector: 'node:parent',
            style: {
                'background-color': (node) => getTypeVisual(node.data('type')).fill,
                'background-opacity': 0.10,
                'border-color': (node) => typeColors[node.data('type')] || '#64748b',
                'border-opacity': 0.5,
                'border-style': 'solid',
                'border-width': 1.5,
                'color': darkMode ? '#e2e8f0' : '#334155',
                'font-size': 11,
                'font-weight': 700,
                'label': nodeLabelToggle && nodeLabelToggle.checked ? 'data(display_label)' : '',
                'padding': 26,
                'shape': 'round-rectangle',
                'text-background-opacity': 0,
                'text-halign': 'center',
                'text-margin-y': -8,
                'text-valign': 'top',
            },
        },
        {
            selector: 'node[status_tone = "healthy"]',
            style: {
                'border-color': '#10b981',
                'border-width': 2.4,
            },
        },
        {
            selector: 'node[status_tone = "warning"]',
            style: {
                'border-color': '#f59e0b',
                'border-width': 2.4,
            },
        },
        {
            selector: 'node[status_tone = "critical"]',
            style: {
                'border-color': '#ef4444',
                'border-width': 3,
            },
        },
        {
            selector: 'edge',
            style: {
                'curve-style': 'bezier',
                'font-family': 'Inter, sans-serif',
                'font-size': 8,
                'label': edgeLabelToggle && edgeLabelToggle.checked ? 'data(label)' : '',
                'line-color': (edge) => edgeColors[edge.data('relationship')] || '#cbd5e1',
                'line-opacity': 0.68,
                'min-zoomed-font-size': 7,
                'overlay-opacity': 0,
                'target-arrow-color': (edge) => edgeColors[edge.data('relationship')] || '#cbd5e1',
                'target-arrow-shape': 'triangle',
                'arrow-scale': 0.82,
                'text-background-color': labelBackground,
                'text-background-opacity': 0.9,
                'text-background-padding': 2,
                'text-rotation': 'autorotate',
                'width': 1.6,
            },
        },
        {
            selector: '.dimmed',
            style: {
                'opacity': 0.12,
                'text-opacity': 0.08,
            },
        },
        {
            selector: '.focused',
            style: {
                'opacity': 1,
                'text-opacity': 1,
                'z-index': 999,
            },
        },
        {
            selector: '.search-match',
            style: {
                'border-color': '#eab308',
                'border-width': 4.5,
                'opacity': 1,
                'z-index': 1000,
            },
        },
        {
            selector: ':selected',
            style: {
                'border-color': '#1d4ed8',
                'border-width': 4.5,
                'line-color': '#1d4ed8',
                'target-arrow-color': '#1d4ed8',
                'z-index': 1200,
            },
        },
        ]
    }

    const layoutOptions = () => {
        const mode = getLayoutMode()
        if (mode === 'dependency') {
            return {
                name: 'cose',
                animate: 'end',
                animationDuration: 420,
                animationEasing: 'ease-out',
                fit: true,
                nodeDimensionsIncludeLabels: true,
                padding: 64,
                idealEdgeLength: 110,
                edgeElasticity: 120,
                nodeRepulsion: 260000,
                gravity: 0.55,
                numIter: 1200,
                componentSpacing: 84,
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
            padding: 48,
            spacingFactor: 1.42,
        }
    }

    const prepareElements = (payload) => {
        const rawNodes = Array.isArray(payload.nodes) ? payload.nodes : []
        const rawEdges = Array.isArray(payload.edges) ? payload.edges : []
        const nodeIds = new Set(rawNodes.map((node) => node?.data?.id).filter(Boolean))
        const containmentEdges = []

        const nodes = rawNodes.map((node) => {
            const data = { ...(node.data || {}) }
            data.display_label = formatNodeLabel(data.label || data.id)
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

        const existingEdgeIds = new Set(rawEdges.map((edge) => edge?.data?.id).filter(Boolean))
        const edges = [
            ...rawEdges,
            ...containmentEdges.filter((edge) => !existingEdgeIds.has(edge.data.id)),
        ]

        return { nodes, edges, elements: [...nodes, ...edges] }
    }

    const ensureCanvasDimensions = () => {
        const parent = canvas?.parentElement
        if (!canvas || !parent) {
            return { width: 0, height: 0 }
        }

        const parentRect = parent.getBoundingClientRect()
        if (parentRect.height < 320) {
            parent.style.minHeight = '720px'
        }

        const canvasRect = canvas.getBoundingClientRect()
        if (canvasRect.height < 320) {
            canvas.style.minHeight = '720px'
        }

        return canvas.getBoundingClientRect()
    }

    const hasRenderableGeometry = () => {
        if (!cy || cy.nodes().length === 0) {
            return false
        }

        const positionsAreFinite = cy.nodes().every((node) => {
            const position = node.position()
            return Number.isFinite(position.x) && Number.isFinite(position.y)
        })
        const bounds = cy.elements().boundingBox()
        return positionsAreFinite && Number.isFinite(bounds.w) && Number.isFinite(bounds.h)
    }

    const applyFallbackLayout = () => {
        if (!cy) {
            return
        }

        cy.layout({
            name: 'grid',
            animate: false,
            avoidOverlap: true,
            condense: false,
            fit: true,
            nodeDimensionsIncludeLabels: true,
            padding: 48,
            spacingFactor: 1.2,
        }).run()
    }


    const getLayoutMode = () => {
        const value = layoutModeSelect?.value || 'hierarchy'
        return value === 'dependency' ? 'dependency' : 'hierarchy'
    }

    const syncLayoutModeFromUrl = () => {
        if (!layoutModeSelect) return
        const url = new URL(window.location.href)
        const value = url.searchParams.get('layout')
        layoutModeSelect.value = value === 'dependency' ? 'dependency' : 'hierarchy'
    }

    const updateNamespaceOptions = (selectedValue = '') => {
        const clusterId = clusterSelect.value
        const namespaces = config.namespace_map[clusterId] || []

        namespaceSelect.innerHTML = ''
        const allOption = document.createElement('option')
        allOption.value = ''
        allOption.textContent = 'All Namespaces'
        namespaceSelect.appendChild(allOption)

        namespaces.forEach((namespace) => {
            const option = document.createElement('option')
            option.value = namespace
            option.textContent = namespace
            option.selected = namespace === selectedValue
            namespaceSelect.appendChild(option)
        })

        namespaceSelect.disabled = !clusterId
        if (!clusterId) {
            namespaceSelect.value = ''
        }
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
            if (value && !(key === 'scope' && value === 'all') && !(key === 'depth' && value === '1') && !(key === 'layout' && value === 'hierarchy')) {
                url.searchParams.set(key, value)
            } else {
                url.searchParams.delete(key)
            }
        })

        window.history.replaceState({}, '', url)
    }

    const updateSummary = (payload) => {
        const summary = payload.summary || {}
        document.getElementById('topology-hero-clusters').textContent = summary.clusters ?? 0
        document.getElementById('topology-hero-namespaces').textContent = summary.namespaces ?? 0
        document.getElementById('topology-hero-resources').textContent = summary.resources ?? 0
        document.getElementById('topology-hero-relationships').textContent = summary.relationships ?? 0
        document.getElementById('topology-hero-collected').textContent = summary.last_collected_at
            ? formatDateTime(summary.last_collected_at)
            : 'No snapshot'
        filterSummary.textContent = `${summary.scope_label || 'All Resources'} · ${summary.depth_label || '1 Level'}`

        document.querySelectorAll('[data-topology-count-type]').forEach((element) => {
            const resourceType = element.dataset.topologyCountType
            element.textContent = payload.type_counts?.[resourceType] ?? 0
        })

        if (summary.truncated) {
            limitWarning.classList.remove('hidden')
            limitMessage.textContent = `${summary.omitted_nodes || 0} resources were omitted to keep the graph readable. Narrow the cluster or namespace scope to display them.`
        } else {
            limitWarning.classList.add('hidden')
        }
    }


    const renderValueRows = (fields, type) => {
        const ui = getTypeUi(type)
        return fields.map((field) => `
            <div class="flex items-start justify-between gap-3 border-b border-slate-100 py-2.5 last:border-b-0 dark:border-slate-700/70">
                <dt class="text-xs font-normal text-slate-500 dark:text-slate-400">${escapeHtml(field.label)}</dt>
                <dd class="max-w-[12rem] break-words text-right text-xs font-normal ${ui.valueClasses}">${escapeHtml(field.value)}</dd>
            </div>
        `).join('')
    }

    const typeStatusPills = (type, status, tone) => {
        const ui = getTypeUi(type)
        const toneClass = statusClasses[tone] || statusClasses.unknown
        return `
            <div class="mt-2 flex flex-wrap items-center gap-2">
                <span class="rounded-full border px-2.5 py-1 text-[10px] font-medium ${ui.softBadgeClasses}">${escapeHtml(humanizeType(type))}</span>
                <span class="rounded-full border px-2.5 py-1 text-[10px] font-medium ${toneClass}">${escapeHtml(status || 'Unknown')}</span>
            </div>
        `
    }

    const emptyDetailHtml = () => `
        <div class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center dark:border-slate-600 dark:bg-slate-900/40">
            <i data-lucide="mouse-pointer-click" class="mx-auto h-7 w-7 text-slate-400"></i>
            <p class="mt-3 text-sm font-medium text-slate-700 dark:text-slate-200">Nothing selected</p>
            <p class="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">Click a graph node to inspect identity, status, inventory fields, and related workspace links.</p>
        </div>
    `

    const renderRelationshipRows = (node) => {
        const visibleEdges = node.connectedEdges().filter((edge) => edge.visible())
        if (visibleEdges.length === 0) {
            return `
                <div class="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center dark:border-slate-600 dark:bg-slate-900/40">
                    <i data-lucide="unlink" class="mx-auto h-5 w-5 text-slate-400"></i>
                    <p class="mt-2 text-xs font-medium text-slate-700 dark:text-slate-200">No visible relationships</p>
                    <p class="mt-1 text-[10px] leading-4 text-slate-500 dark:text-slate-400">Enable relationship types from the left panel to include them here.</p>
                </div>
            `
        }

        return visibleEdges.map((edge) => {
            const edgeData = edge.data()
            const sourceIsSelected = edge.source().id() === node.id()
            const peer = sourceIsSelected ? edge.target() : edge.source()
            const peerData = peer.data()
            const relUi = getRelationshipUi(edgeData.relationship)
            const color = edgeColors[edgeData.relationship] || '#64748b'
            const direction = sourceIsSelected ? 'Outbound' : 'Inbound'

            return `
                <button type="button"
                        data-topology-related-node="${escapeHtml(peer.id())}"
                        class="flex w-full items-start gap-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-left transition hover:border-blue-200 hover:bg-blue-50/50 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-blue-500/30 dark:hover:bg-blue-500/10">
                    <span class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl border ${relUi.badgeClasses}">
                        <i data-lucide="${escapeHtml(relUi.icon)}" class="h-4 w-4"></i>
                    </span>
                    <span class="min-w-0 flex-1">
                        <span class="flex flex-wrap items-center gap-2">
                            <span class="text-[10px] font-medium uppercase tracking-wide text-slate-400">${escapeHtml(direction)}</span>
                            <span class="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[9px] font-medium ${relUi.badgeClasses}">
                                <span class="h-1.5 w-1.5 rounded-full" style="background:${color}"></span>
                                ${escapeHtml(edgeData.label || edgeData.relationship)}
                            </span>
                        </span>
                        <span class="mt-1 block break-words text-xs font-medium text-slate-900 dark:text-white">${escapeHtml(peerData.label || peer.id())}</span>
                        <span class="mt-1 block text-[10px] text-slate-500 dark:text-slate-400">${escapeHtml(humanizeType(peerData.type))}</span>
                    </span>
                    <i data-lucide="chevron-right" class="mt-2 h-3.5 w-3.5 flex-shrink-0 text-slate-400"></i>
                </button>
            `
        }).join('')
    }

    const renderNodeDetails = (node, initialTab = 'details') => {
        const data = node.data()
        const connectedEdges = node.connectedEdges().filter((edge) => edge.visible()).length
        const fields = Array.isArray(data.fields) ? data.fields : []
        const ui = getTypeUi(data.type)
        const fieldRows = renderValueRows(fields, data.type)
        selectedNodeId = node.id()

        const detailsHtml = `
            <div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
                <div class="flex items-center justify-between gap-3">
                    <h5 class="text-xs font-semibold text-slate-900 dark:text-white">Resource context</h5>
                    <span class="rounded-full border px-2.5 py-1 text-[10px] font-medium ${ui.softBadgeClasses}">${connectedEdges} relationships</span>
                </div>
                <dl class="mt-3">
                    <div class="flex items-start justify-between gap-3 border-b border-slate-100 py-2.5 dark:border-slate-700/70">
                        <dt class="text-xs font-normal text-slate-500 dark:text-slate-400">Cluster</dt>
                        <dd class="max-w-[12rem] break-words text-right text-xs font-normal ${ui.valueClasses}">${escapeHtml(data.cluster_name || 'Not reported')}</dd>
                    </div>
                    ${data.namespace ? `
                        <div class="flex items-start justify-between gap-3 border-b border-slate-100 py-2.5 dark:border-slate-700/70">
                            <dt class="text-xs font-normal text-slate-500 dark:text-slate-400">Namespace</dt>
                            <dd class="max-w-[12rem] break-words text-right text-xs font-normal ${ui.valueClasses}">${escapeHtml(data.namespace)}</dd>
                        </div>
                    ` : ''}
                    ${fieldRows}
                    <div class="flex items-start justify-between gap-3 py-2.5">
                        <dt class="text-xs font-normal text-slate-500 dark:text-slate-400">Collected</dt>
                        <dd class="max-w-[12rem] break-words text-right text-xs font-normal ${ui.valueClasses}">${escapeHtml(formatDateTime(data.collected_at))}</dd>
                    </div>
                </dl>
            </div>

            ${data.action_url ? `
                <a href="${escapeHtml(data.action_url)}" class="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700">
                    Open ${escapeHtml(humanizeType(data.type))} Inventory
                    <i data-lucide="arrow-up-right" class="h-4 w-4"></i>
                </a>
            ` : ''}
        `

        const relationshipsHtml = `
            <div class="space-y-2">
                ${renderRelationshipRows(node)}
            </div>
        `

        detailContent.innerHTML = `
            <div class="space-y-4">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
                    <div class="flex items-start gap-3">
                        <span class="mt-0.5 flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl ring-1 ${ui.iconClasses}">
                            <i data-lucide="${escapeHtml(ui.icon)}" class="h-5 w-5"></i>
                        </span>
                        <div class="min-w-0 flex-1">
                            <h4 class="break-words text-sm font-semibold text-slate-950 dark:text-white">${escapeHtml(data.label)}</h4>
                            <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">${escapeHtml(data.kind || humanizeType(data.type))}</p>
                            ${typeStatusPills(data.type, data.status, data.status_tone)}
                        </div>
                    </div>
                    ${data.description ? `<p class="mt-3 text-xs leading-5 text-slate-600 dark:text-slate-300">${escapeHtml(data.description)}</p>` : ''}
                </div>

                <div class="grid grid-cols-2 rounded-xl border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-900/60">
                    <button type="button" data-topology-node-tab="details" class="rounded-lg px-3 py-2 text-xs font-medium transition">Details</button>
                    <button type="button" data-topology-node-tab="relationships" class="rounded-lg px-3 py-2 text-xs font-medium transition">Relationships <span class="ml-1 text-[10px] opacity-70">${connectedEdges}</span></button>
                </div>

                <div id="topology-node-tab-panel"></div>
            </div>
        `

        const panel = detailContent.querySelector('#topology-node-tab-panel')
        const buttons = Array.from(detailContent.querySelectorAll('[data-topology-node-tab]'))
        const activateTab = (tabName) => {
            const selectedTab = tabName === 'relationships' ? 'relationships' : 'details'
            panel.innerHTML = selectedTab === 'relationships' ? relationshipsHtml : detailsHtml
            buttons.forEach((button) => {
                const active = button.dataset.topologyNodeTab === selectedTab
                button.className = active
                    ? 'rounded-lg bg-white px-3 py-2 text-xs font-semibold text-blue-700 shadow-sm dark:bg-slate-800 dark:text-blue-300'
                    : 'rounded-lg px-3 py-2 text-xs font-medium text-slate-500 transition hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
            })

            panel.querySelectorAll('[data-topology-related-node]').forEach((button) => {
                button.addEventListener('click', () => {
                    const relatedNode = cy?.getElementById(button.dataset.topologyRelatedNode)
                    if (relatedNode && relatedNode.length) {
                        focusNeighborhood(relatedNode)
                        renderNodeDetails(relatedNode, 'relationships')
                        cy.animate({ center: { eles: relatedNode }, zoom: Math.max(cy.zoom(), 1.1) }, { duration: 220 })
                    }
                })
            })

            if (window.lucide) {
                window.lucide.createIcons()
            }
        }

        buttons.forEach((button) => {
            button.addEventListener('click', () => activateTab(button.dataset.topologyNodeTab))
        })
        activateTab(initialTab)
    }

    const renderEdgeDetails = (edge) => {
        const data = edge.data()
        const color = edgeColors[data.relationship] || '#64748b'
        const ui = getRelationshipUi(data.relationship)
        detailContent.innerHTML = `
            <div class="space-y-4">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
                    <div class="flex items-start gap-3">
                        <span class="flex h-11 w-11 items-center justify-center rounded-2xl ring-1 ${ui.badgeClasses}">
                            <i data-lucide="${escapeHtml(ui.icon)}" class="h-5 w-5"></i>
                        </span>
                        <div class="min-w-0 flex-1">
                            <h4 class="break-words text-sm font-semibold text-slate-950 dark:text-white">${escapeHtml(data.label || 'Relationship')}</h4>
                            <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">Topology relationship</p>
                            <div class="mt-2 inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px] font-medium ${ui.badgeClasses}">
                                <span class="h-2 w-2 rounded-full" style="background:${color}"></span>
                                ${escapeHtml(data.relationship || 'relationship')}
                            </div>
                        </div>
                    </div>
                    ${data.description ? `<p class="mt-3 text-xs leading-5 text-slate-600 dark:text-slate-300">${escapeHtml(data.description)}</p>` : ''}
                </div>

                <div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
                    <div class="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-900/40">
                        <span class="h-3 w-3 rounded-full" style="background:${color}"></span>
                        <div class="min-w-0 flex-1 space-y-1">
                            <p class="break-words text-xs font-medium text-slate-900 dark:text-white">${escapeHtml(data.source_label)}</p>
                            <p class="text-[10px] font-medium uppercase tracking-wide text-slate-400">${escapeHtml(data.label)}</p>
                            <p class="break-words text-xs font-medium text-slate-900 dark:text-white">${escapeHtml(data.target_label)}</p>
                        </div>
                    </div>
                </div>
            </div>
        `

        if (window.lucide) {
            window.lucide.createIcons()
        }
    }

    const clearFocus = () => {
        if (!cy) {
            return
        }
        cy.elements().removeClass('dimmed focused')
        cy.elements().unselect()
    }

    const focusNeighborhood = (node) => {
        clearFocus()
        const neighborhood = node.closedNeighborhood()
        cy.elements().addClass('dimmed')
        neighborhood.removeClass('dimmed').addClass('focused')
        node.select()
    }

    const attachGraphEvents = () => {
        cy.on('tap', 'node', (event) => {
            const node = event.target
            selectedNodeId = node.id()
            focusNeighborhood(node)
            renderNodeDetails(node)
        })

        cy.on('tap', 'edge', (event) => {
            selectedNodeId = null
            clearFocus()
            const edge = event.target
            edge.select()
            edge.connectedNodes().addClass('focused')
            renderEdgeDetails(edge)
        })

        cy.on('tap', (event) => {
            if (event.target !== cy) {
                return
            }
            selectedNodeId = null
            clearFocus()
            detailContent.innerHTML = emptyDetailHtml()
            if (window.lucide) {
                window.lucide.createIcons()
            }
        })
    }

    const setRuntimeStatus = (message = '') => {
        if (!runtimeStatus) {
            return
        }

        if (!message) {
            runtimeStatus.classList.add('hidden')
            runtimeStatus.innerHTML = ''
            return
        }

        runtimeStatus.classList.remove('hidden')
        runtimeStatus.innerHTML = `<span class="inline-flex items-center gap-2"><span class="h-2 w-2 rounded-full bg-blue-500"></span>${escapeHtml(message)}</span>`
    }

    const enabledRelationshipTypes = () => new Set(
        relationshipToggles
            .filter((toggle) => toggle.checked)
            .map((toggle) => toggle.dataset.topologyRelationshipToggle)
    )

    const applyRelationshipVisibility = ({ relayout = false } = {}) => {
        if (!cy) return

        const enabled = enabledRelationshipTypes()
        cy.edges().forEach((edge) => {
            const visible = enabled.has(edge.data('relationship'))
            edge.style('display', visible ? 'element' : 'none')
        })

        if (selectedNodeId) {
            const selectedNode = cy.getElementById(selectedNodeId)
            if (selectedNode && selectedNode.length) {
                renderNodeDetails(selectedNode, 'relationships')
            }
        }

        if (relayout) {
            applyCurrentLayout()
        }
    }

    const fitGraphToCanvas = () => {
        if (!cy) return

        const visibleElements = cy.elements(':visible')
        if (!visibleElements.length) return

        ensureCanvasDimensions()
        cy.resize()

        const canvasRect = canvas.getBoundingClientRect()
        const shortestSide = Math.min(canvasRect.width || 0, canvasRect.height || 0)
        const padding = Math.max(82, Math.min(132, Math.round(shortestSide * 0.12)))

        cy.fit(visibleElements, padding)
    }

    const applyCurrentLayout = () => {
        if (!cy) return

        const visibleElements = cy.elements(':visible')
        if (!visibleElements.length) return

        cy.one('layoutstop', () => {
            requestAnimationFrame(() => {
                fitGraphToCanvas()
                window.setTimeout(fitGraphToCanvas, 180)
            })
        })

        visibleElements.layout(layoutOptions()).run()
        window.setTimeout(fitGraphToCanvas, 360)
    }

    const createGraph = (payload) => {
        currentPayload = payload

        if (cy) {
            cy.destroy()
        }

        const prepared = prepareElements(payload)
        const { nodes, edges, elements } = prepared
        const hasNodes = nodes.length > 0
        emptyState.classList.toggle('hidden', hasNodes)
        emptyState.classList.toggle('flex', !hasNodes)
        updateSummary(payload)

        if (!hasNodes) {
            cy = null
            setRuntimeStatus()
            return
        }

        const canvasRect = ensureCanvasDimensions()
        setRuntimeStatus(`Rendering ${nodes.length} resources and ${edges.length} relationships...`)

        if (canvasRect.width < 100 || canvasRect.height < 100) {
            showError(`Topology canvas is not visible yet (${Math.round(canvasRect.width)} × ${Math.round(canvasRect.height)} px). Resize the browser window or reload the page.`)
        }

        try {
            cy = window.cytoscape({
                container: canvas,
                elements,
                layout: layoutOptions(),
                maxZoom: 2.4,
                minZoom: 0.16,
                pixelRatio: 'auto',
                selectionType: 'single',
                style: graphStyle(),
            })

            attachGraphEvents()
            applyRelationshipVisibility()
            applySearch()

            let renderFinalized = false
            const finalizeRender = () => {
                if (renderFinalized) return
                renderFinalized = true

                window.requestAnimationFrame(() => {
                    ensureCanvasDimensions()
                    cy.resize()

                    if (!hasRenderableGeometry()) {
                        applyFallbackLayout()
                    }

                    window.setTimeout(() => {
                        if (!cy) {
                            return
                        }
                        fitGraphToCanvas()
                        window.setTimeout(fitGraphToCanvas, 160)
                        window.setTimeout(fitGraphToCanvas, 420)
                        window.setTimeout(fitGraphToCanvas, 820)
                        setRuntimeStatus()
                        showError()
                        console.info('KAORI topology rendered.', {
                            resources: cy.nodes().length,
                            relationships: cy.edges().length,
                            canvas: canvas.getBoundingClientRect(),
                        })
                    }, 80)
                })
            }

            cy.one('layoutstop', finalizeRender)
            window.setTimeout(finalizeRender, 250)
        } catch (error) {
            console.error('KAORI could not render topology.', error)
            cy = null
            setRuntimeStatus()
            showError(`Topology renderer failed: ${error.message || 'unknown error'}`)
        }
    }

    const setLoading = (state) => {
        loading.classList.toggle('hidden', !state)
        document.getElementById('topology-refresh-button').disabled = state
    }

    const showError = (message = '') => {
        if (!message) {
            errorPanel.classList.add('hidden')
            errorPanel.textContent = ''
            return
        }
        errorPanel.textContent = message
        errorPanel.classList.remove('hidden')
    }

    const fetchGraph = async () => {
        if (fetchController) {
            fetchController.abort()
        }
        fetchController = new AbortController()
        setLoading(true)
        showError()

        const params = new URLSearchParams({
            cluster_id: clusterSelect.value,
            namespace: namespaceSelect.disabled ? '' : namespaceSelect.value,
            scope: scopeSelect.value,
            depth: depthSelect.value,
            layout: getLayoutMode(),
        })

        try {
            const response = await fetch(`${config.data_url}?${params.toString()}`, {
                credentials: 'same-origin',
                headers: { Accept: 'application/json' },
                signal: fetchController.signal,
            })

            if (!response.ok) {
                throw new Error(`Topology request failed with HTTP ${response.status}.`)
            }

            const payload = await response.json()
            createGraph(payload)
            updateUrl()
        } catch (error) {
            if (error.name !== 'AbortError') {
                showError(error.message || 'KAORI could not load topology data.')
            }
        } finally {
            setLoading(false)
        }
    }

    const applySearch = () => {
        if (!cy) {
            return
        }

        const term = searchInput.value.trim().toLowerCase()
        cy.nodes().removeClass('search-match')

        if (!term) {
            cy.elements().removeClass('dimmed')
            searchSummary.textContent = 'Search highlights resources already loaded in the graph.'
            return
        }

        const matches = cy.nodes().filter((node) => {
            const data = node.data()
            const haystack = [
                data.label,
                data.kind,
                data.type,
                data.cluster_name,
                data.namespace,
                data.status,
            ].filter(Boolean).join(' ').toLowerCase()
            return haystack.includes(term)
        })

        if (matches.length === 0) {
            cy.elements().removeClass('dimmed')
            searchSummary.textContent = 'No matching resource in the current graph.'
            return
        }

        cy.elements().addClass('dimmed')
        matches.removeClass('dimmed').addClass('search-match')
        matches.connectedEdges().removeClass('dimmed')
        matches.connectedEdges().connectedNodes().removeClass('dimmed')
        cy.animate({
            center: { eles: matches.first() },
            zoom: Math.max(cy.zoom(), 1.15),
        }, { duration: 250 })
        searchSummary.textContent = `${matches.length} matching ${matches.length === 1 ? 'resource' : 'resources'} highlighted.`
    }

    if (!canvas || !clusterSelect || !namespaceSelect || !scopeSelect || !depthSelect) {
        return
    }

    if (!window.cytoscape) {
        setRuntimeStatus()
        showError('The local Cytoscape.js renderer could not be loaded. Restart the web service and confirm the static vendor file is present.')
        return
    }


    if (window.ResizeObserver && canvas.parentElement) {
        const topologyResizeObserver = new ResizeObserver(() => {
            if (!cy) {
                return
            }
            cy.resize()
        })
        topologyResizeObserver.observe(canvas.parentElement)
    }

    syncLayoutModeFromUrl()
    updateNamespaceOptions(config.filters?.namespace || '')
    createGraph(currentPayload)

    clusterSelect.addEventListener('change', () => {
        updateNamespaceOptions('')
        fetchGraph()
    })
    namespaceSelect.addEventListener('change', fetchGraph)
    scopeSelect.addEventListener('change', fetchGraph)
    depthSelect.addEventListener('change', fetchGraph)
    layoutModeSelect?.addEventListener('change', () => {
        updateUrl()
        applyCurrentLayout()
    })

    searchInput.addEventListener('input', () => {
        window.clearTimeout(searchTimer)
        searchTimer = window.setTimeout(applySearch, 280)
    })

    document.getElementById('topology-fit-button').addEventListener('click', () => {
        fitGraphToCanvas()
    })

    document.getElementById('topology-reset-button').addEventListener('click', () => {
        if (!cy) {
            return
        }
        searchInput.value = ''
        selectedNodeId = null
        clearFocus()
        cy.nodes().removeClass('search-match')
        detailContent.innerHTML = emptyDetailHtml()
        searchSummary.textContent = 'Search highlights resources already loaded in the graph.'
        applyCurrentLayout()
        if (window.lucide) {
            window.lucide.createIcons()
        }
    })

    document.getElementById('topology-refresh-button').addEventListener('click', fetchGraph)

    nodeLabelToggle.addEventListener('change', () => {
        if (cy) {
            cy.style().selector('node').style('label', nodeLabelToggle.checked ? 'data(display_label)' : '').update()
            cy.style().selector('node:parent').style('label', nodeLabelToggle.checked ? 'data(display_label)' : '').update()
        }
    })

    edgeLabelToggle.addEventListener('change', () => {
        if (cy) {
            cy.style().selector('edge').style('label', edgeLabelToggle.checked ? 'data(label)' : '').update()
        }
    })

    relationshipToggles.forEach((toggle) => {
        toggle.addEventListener('change', () => {
            applyRelationshipVisibility({ relayout: getLayoutMode() === 'dependency' })
        })
    })

    const themeToggle = document.getElementById('theme-toggle')
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            window.setTimeout(() => {
                if (cy) {
                    cy.style(graphStyle())
                }
            }, 0)
        })
    }
})()
