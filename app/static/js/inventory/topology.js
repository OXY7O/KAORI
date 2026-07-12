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
    const emptyState = document.getElementById('topology-empty-state')
    const limitWarning = document.getElementById('topology-limit-warning')
    const limitMessage = document.getElementById('topology-limit-message')
    const detailContent = document.getElementById('topology-detail-content')
    const nodeLabelToggle = document.getElementById('topology-node-label-toggle')
    const edgeLabelToggle = document.getElementById('topology-edge-label-toggle')
    const searchSummary = document.getElementById('topology-search-summary')
    const filterSummary = document.getElementById('topology-filter-summary')

    let cy = null
    let currentPayload = config.initial_graph || { nodes: [], edges: [], summary: {}, type_counts: {} }
    let fetchController = null
    let searchTimer = null

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
    }

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
                'background-color': (node) => typeColors[node.data('type')] || '#64748b',
                'border-color': '#ffffff',
                'border-width': 2,
                'color': labelColor,
                'font-family': 'Inter, sans-serif',
                'font-size': 10,
                'font-weight': 600,
                'height': 38,
                'label': nodeLabelToggle && nodeLabelToggle.checked ? 'data(label)' : '',
                'min-zoomed-font-size': 8,
                'overlay-opacity': 0,
                'shape': 'round-rectangle',
                'text-background-color': labelBackground,
                'text-background-opacity': 0.88,
                'text-background-padding': 3,
                'text-halign': 'center',
                'text-margin-y': 8,
                'text-max-width': 118,
                'text-overflow-wrap': 'ellipsis',
                'text-valign': 'bottom',
                'text-wrap': 'wrap',
                'width': 44,
            },
        },
        {
            selector: 'node[type = "pod"]',
            style: {
                'shape': 'ellipse',
                'height': 34,
                'width': 34,
            },
        },
        {
            selector: 'node[type = "service"]',
            style: {
                'shape': 'diamond',
                'height': 42,
                'width': 42,
            },
        },
        {
            selector: 'node[type = "ingress"]',
            style: {
                'shape': 'hexagon',
                'height': 44,
                'width': 44,
            },
        },
        {
            selector: 'node[type = "configmap"], node[type = "secret"]',
            style: {
                'shape': 'round-tag',
                'height': 38,
                'width': 46,
            },
        },
        {
            selector: 'node[type = "pvc"], node[type = "pv"]',
            style: {
                'shape': 'barrel',
                'height': 42,
                'width': 42,
            },
        },
        {
            selector: 'node:parent',
            style: {
                'background-color': (node) => typeColors[node.data('type')] || '#64748b',
                'background-opacity': 0.06,
                'border-color': (node) => typeColors[node.data('type')] || '#64748b',
                'border-opacity': 0.5,
                'border-style': 'solid',
                'border-width': 1.5,
                'color': darkMode ? '#e2e8f0' : '#334155',
                'font-size': 11,
                'font-weight': 700,
                'label': nodeLabelToggle && nodeLabelToggle.checked ? 'data(label)' : '',
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
                'border-width': 3,
            },
        },
        {
            selector: 'node[status_tone = "warning"]',
            style: {
                'border-color': '#f59e0b',
                'border-width': 3,
            },
        },
        {
            selector: 'node[status_tone = "critical"]',
            style: {
                'border-color': '#ef4444',
                'border-width': 4,
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
                'line-opacity': 0.74,
                'min-zoomed-font-size': 7,
                'overlay-opacity': 0,
                'target-arrow-color': (edge) => edgeColors[edge.data('relationship')] || '#cbd5e1',
                'target-arrow-shape': 'triangle',
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
                'border-width': 5,
                'opacity': 1,
                'z-index': 1000,
            },
        },
        {
            selector: ':selected',
            style: {
                'border-color': '#1d4ed8',
                'border-width': 5,
                'line-color': '#1d4ed8',
                'target-arrow-color': '#1d4ed8',
                'z-index': 1200,
            },
        },
        ]
    }

    const layoutOptions = () => ({
        name: 'cose',
        animate: false,
        componentSpacing: 90,
        fit: true,
        gravity: 0.25,
        idealEdgeLength: 100,
        nestingFactor: 1.3,
        nodeDimensionsIncludeLabels: true,
        nodeOverlap: 26,
        nodeRepulsion: 7000,
        numIter: 900,
        padding: 42,
        randomize: true,
    })

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
        }

        Object.entries(values).forEach(([key, value]) => {
            if (value && !(key === 'scope' && value === 'all') && !(key === 'depth' && value === '2')) {
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
        filterSummary.textContent = `${summary.scope_label || 'All Resources'} · ${summary.depth_label || '2 Levels'}`

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

    const emptyDetailHtml = () => `
        <div class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center dark:border-slate-600 dark:bg-slate-900/40">
            <i data-lucide="mouse-pointer-click" class="mx-auto h-7 w-7 text-slate-400"></i>
            <p class="mt-3 text-sm font-medium text-slate-700 dark:text-slate-200">Nothing selected</p>
            <p class="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">Click a graph node to inspect identity, status, inventory fields, and related workspace links.</p>
        </div>
    `

    const renderNodeDetails = (node) => {
        const data = node.data()
        const connectedEdges = node.connectedEdges().length
        const toneClass = statusClasses[data.status_tone] || statusClasses.unknown
        const fields = Array.isArray(data.fields) ? data.fields : []
        const fieldRows = fields.map((field) => `
            <div class="flex items-start justify-between gap-3 border-b border-slate-100 py-2.5 last:border-b-0 dark:border-slate-700/70">
                <dt class="text-xs text-slate-500 dark:text-slate-400">${escapeHtml(field.label)}</dt>
                <dd class="max-w-[12rem] break-words text-right text-xs font-medium text-slate-800 dark:text-slate-100">${escapeHtml(field.value)}</dd>
            </div>
        `).join('')

        detailContent.innerHTML = `
            <div class="space-y-4">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
                    <div class="flex items-start gap-3">
                        <span class="mt-0.5 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-white shadow-sm ring-1 ring-slate-200 dark:bg-slate-800 dark:ring-slate-700">
                            <span class="h-3 w-3 rounded-full" style="background:${typeColors[data.type] || '#64748b'}"></span>
                        </span>
                        <div class="min-w-0 flex-1">
                            <div class="flex flex-wrap items-center gap-2">
                                <h4 class="break-words text-sm font-semibold text-slate-950 dark:text-white">${escapeHtml(data.label)}</h4>
                                <span class="rounded-full border px-2 py-0.5 text-[10px] font-medium ${toneClass}">${escapeHtml(data.status || 'Unknown')}</span>
                            </div>
                            <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">${escapeHtml(data.kind || humanizeType(data.type))}</p>
                        </div>
                    </div>
                    <p class="mt-3 text-xs leading-5 text-slate-600 dark:text-slate-300">${escapeHtml(data.description || '')}</p>
                </div>

                <div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
                    <div class="flex items-center justify-between gap-3">
                        <h5 class="text-xs font-semibold text-slate-900 dark:text-white">Inventory context</h5>
                        <span class="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-700 ring-1 ring-inset ring-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20">${connectedEdges} relationships</span>
                    </div>
                    <dl class="mt-3">
                        <div class="flex items-start justify-between gap-3 border-b border-slate-100 py-2.5 dark:border-slate-700/70">
                            <dt class="text-xs text-slate-500 dark:text-slate-400">Cluster</dt>
                            <dd class="max-w-[12rem] break-words text-right text-xs font-medium text-slate-800 dark:text-slate-100">${escapeHtml(data.cluster_name || 'Not reported')}</dd>
                        </div>
                        ${data.namespace ? `
                            <div class="flex items-start justify-between gap-3 border-b border-slate-100 py-2.5 dark:border-slate-700/70">
                                <dt class="text-xs text-slate-500 dark:text-slate-400">Namespace</dt>
                                <dd class="max-w-[12rem] break-words text-right text-xs font-medium text-slate-800 dark:text-slate-100">${escapeHtml(data.namespace)}</dd>
                            </div>
                        ` : ''}
                        ${fieldRows}
                        <div class="flex items-start justify-between gap-3 py-2.5">
                            <dt class="text-xs text-slate-500 dark:text-slate-400">Collected</dt>
                            <dd class="max-w-[12rem] break-words text-right text-xs font-medium text-slate-800 dark:text-slate-100">${escapeHtml(formatDateTime(data.collected_at))}</dd>
                        </div>
                    </dl>
                </div>

                ${data.action_url ? `
                    <a href="${escapeHtml(data.action_url)}" class="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700">
                        Open ${escapeHtml(humanizeType(data.type))} Inventory
                        <i data-lucide="arrow-up-right" class="h-4 w-4"></i>
                    </a>
                ` : ''}
            </div>
        `

        if (window.lucide) {
            window.lucide.createIcons()
        }
    }

    const renderEdgeDetails = (edge) => {
        const data = edge.data()
        const color = edgeColors[data.relationship] || '#64748b'
        detailContent.innerHTML = `
            <div class="space-y-4">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
                    <div class="flex items-center gap-3">
                        <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm ring-1 ring-slate-200 dark:bg-slate-800 dark:ring-slate-700">
                            <i data-lucide="git-commit-horizontal" class="h-5 w-5 text-slate-500"></i>
                        </span>
                        <div>
                            <h4 class="text-sm font-semibold text-slate-950 dark:text-white">${escapeHtml(data.label || 'Relationship')}</h4>
                            <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">Topology relationship</p>
                        </div>
                    </div>
                    <p class="mt-3 text-xs leading-5 text-slate-600 dark:text-slate-300">${escapeHtml(data.description || '')}</p>
                </div>

                <div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
                    <div class="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-3 dark:bg-slate-900/40">
                        <span class="h-3 w-3 rounded-full" style="background:${color}"></span>
                        <div class="min-w-0 flex-1">
                            <p class="break-words text-xs font-semibold text-slate-900 dark:text-white">${escapeHtml(data.source_label)}</p>
                            <p class="mt-1 text-[10px] font-medium uppercase tracking-wide text-slate-400">${escapeHtml(data.label)}</p>
                            <p class="mt-1 break-words text-xs font-semibold text-slate-900 dark:text-white">${escapeHtml(data.target_label)}</p>
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
            focusNeighborhood(node)
            renderNodeDetails(node)
        })

        cy.on('tap', 'edge', (event) => {
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
            clearFocus()
            detailContent.innerHTML = emptyDetailHtml()
            if (window.lucide) {
                window.lucide.createIcons()
            }
        })
    }

    const createGraph = (payload) => {
        currentPayload = payload

        if (cy) {
            cy.destroy()
        }

        const elements = [...(payload.nodes || []), ...(payload.edges || [])]
        const hasNodes = (payload.nodes || []).length > 0
        emptyState.classList.toggle('hidden', hasNodes)
        emptyState.classList.toggle('flex', !hasNodes)

        cy = window.cytoscape({
            container: canvas,
            elements,
            layout: layoutOptions(),
            maxZoom: 2.4,
            minZoom: 0.16,
            pixelRatio: 'auto',
            selectionType: 'single',
            style: graphStyle(),
            wheelSensitivity: 0.18,
        })

        attachGraphEvents()
        updateSummary(payload)
        applySearch()
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
        showError('Cytoscape.js could not be loaded. Check browser access to the configured CDN or vendor the library locally.')
        return
    }

    updateNamespaceOptions(config.filters?.namespace || '')
    createGraph(currentPayload)

    clusterSelect.addEventListener('change', () => {
        updateNamespaceOptions('')
        fetchGraph()
    })
    namespaceSelect.addEventListener('change', fetchGraph)
    scopeSelect.addEventListener('change', fetchGraph)
    depthSelect.addEventListener('change', fetchGraph)

    searchInput.addEventListener('input', () => {
        window.clearTimeout(searchTimer)
        searchTimer = window.setTimeout(applySearch, 280)
    })

    document.getElementById('topology-fit-button').addEventListener('click', () => {
        if (cy) {
            cy.fit(undefined, 38)
        }
    })

    document.getElementById('topology-reset-button').addEventListener('click', () => {
        if (!cy) {
            return
        }
        searchInput.value = ''
        clearFocus()
        cy.nodes().removeClass('search-match')
        detailContent.innerHTML = emptyDetailHtml()
        searchSummary.textContent = 'Search highlights resources already loaded in the graph.'
        cy.layout(layoutOptions()).run()
        if (window.lucide) {
            window.lucide.createIcons()
        }
    })

    document.getElementById('topology-refresh-button').addEventListener('click', fetchGraph)

    nodeLabelToggle.addEventListener('change', () => {
        if (cy) {
            cy.style().selector('node').style('label', nodeLabelToggle.checked ? 'data(label)' : '').update()
            cy.style().selector('node:parent').style('label', nodeLabelToggle.checked ? 'data(label)' : '').update()
        }
    })

    edgeLabelToggle.addEventListener('change', () => {
        if (cy) {
            cy.style().selector('edge').style('label', edgeLabelToggle.checked ? 'data(label)' : '').update()
        }
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
