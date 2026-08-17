;(() => {
    const CHART_KEY = 'kaoriUtilizationTrendChart'
    const MAX_VISIBILITY_RETRIES = 12
    let observedContainer = null

    const cssVariable = (name, fallback) =>
        getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback

    function trendPanel(root = document) {
        if (root?.id === 'utilization-trend-panel' && root.isConnected) return root
        return root?.querySelector?.('#utilization-trend-panel') || document.getElementById('utilization-trend-panel')
    }

    function parseTrendData(panel) {
        const source = panel?.querySelector('[data-utilization-trend-data]')
        if (!source) return null
        try {
            return JSON.parse(source.textContent || '{}')
        } catch (error) {
            console.error('Unable to parse utilization trend data.', error)
            return null
        }
    }

    function destroyChart() {
        if (window[CHART_KEY]) {
            window[CHART_KEY].destroy()
            window[CHART_KEY] = null
        }
    }

    function chartContainer(panel) {
        return panel?.querySelector('#utilizationTrendChartContainer') || null
    }

    function isTrendRenderable(panel, container) {
        if (!panel?.isConnected || !container?.isConnected || panel.hidden) return false
        const panelStyle = window.getComputedStyle(panel)
        const containerStyle = window.getComputedStyle(container)
        if (panelStyle.display === 'none' || panelStyle.visibility === 'hidden') return false
        if (containerStyle.display === 'none' || containerStyle.visibility === 'hidden') return false
        const bounds = container.getBoundingClientRect()
        return bounds.width > 0 && bounds.height > 0
    }

    function observeContainer(container) {
        if (typeof ResizeObserver === 'undefined' || !container || observedContainer === container) return

        if (observedContainer) resizeObserver.unobserve(observedContainer)
        observedContainer = container
        resizeObserver.observe(container)
    }

    function normalizedPoints(values) {
        if (!Array.isArray(values)) return []
        return values
            .filter((item) => Number.isFinite(Number(item?.timestamp)) && Number.isFinite(Number(item?.value)))
            .map((item) => ({ timestamp: Number(item.timestamp), value: Number(item.value) }))
            .sort((left, right) => left.timestamp - right.timestamp)
    }

    function alignedSeries(series) {
        const timestamps = [...new Set(series.flatMap(([, values]) => values.map((point) => point.timestamp)))].sort(
            (left, right) => left - right
        )

        return {
            timestamps,
            datasets: series.map(([label, values, color]) => {
                const byTimestamp = new Map(values.map((point) => [point.timestamp, point.value]))
                return {
                    label,
                    color,
                    values: timestamps.map((timestamp) => byTimestamp.get(timestamp) ?? null),
                }
            }),
        }
    }

    function formatTimestamp(timestamp, trendHours) {
        const longWindow = Number(trendHours) > 24
        return new Intl.DateTimeFormat(
            [],
            longWindow
                ? { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }
                : { hour: '2-digit', minute: '2-digit' }
        ).format(new Date(timestamp * 1000))
    }

    function renderTrendChart(root = document) {
        const panel = trendPanel(root)
        const canvas = panel?.querySelector('#utilizationTrendChart')
        const container = chartContainer(panel)
        const data = parseTrendData(panel)
        if (!panel || !canvas || !container || !data || typeof Chart === 'undefined') return false

        observeContainer(container)
        if (!isTrendRenderable(panel, container)) return false

        const rawSeries = [
            ['CPU', normalizedPoints(data.cpu), cssVariable('--kaori-brand-primary', 'CanvasText')],
            ['Memory', normalizedPoints(data.memory), cssVariable('--kaori-status-normal', 'CanvasText')],
            ['Pods', normalizedPoints(data.pods), cssVariable('--kaori-status-pending', 'CanvasText')],
        ]
        const hasData = rawSeries.some(([, values]) => values.length)
        const emptyState = panel.querySelector('#trendEmptyState')

        if (!hasData) {
            destroyChart()
            container.classList.add('hidden')
            emptyState?.classList.remove('hidden')
            return true
        }

        const aligned = alignedSeries(rawSeries)
        const observedValues = rawSeries.flatMap(([, values]) => values.map((point) => point.value))
        const observedMaximum = Math.max(100, ...observedValues)
        const suggestedMaximum = Math.ceil(observedMaximum / 10) * 10

        container.classList.remove('hidden')
        emptyState?.classList.add('hidden')
        destroyChart()

        canvas.style.width = '100%'
        canvas.style.height = '100%'

        const ratio = Math.min(window.devicePixelRatio || 1, 2)
        const cardColor = cssVariable('--kaori-surface-card', 'Canvas')
        const textColor = cssVariable('--kaori-content-secondary', 'CanvasText')
        const primaryColor = cssVariable('--kaori-content-primary', 'CanvasText')
        const gridColor = cssVariable('--kaori-outline-subtle', 'transparent')
        const labels = aligned.timestamps.map((timestamp) => formatTimestamp(timestamp, data.trend_hours))

        window[CHART_KEY] = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels,
                datasets: aligned.datasets.map((dataset) => ({
                    label: dataset.label,
                    data: dataset.values,
                    borderColor: dataset.color,
                    backgroundColor: dataset.color,
                    pointBackgroundColor: dataset.color,
                    pointBorderColor: cardColor,
                    pointBorderWidth: 2,
                    pointRadius: 2.5,
                    pointHoverRadius: 5,
                    borderWidth: 3,
                    fill: false,
                    spanGaps: true,
                    tension: 0.35,
                })),
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                normalized: true,
                devicePixelRatio: ratio,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: cardColor,
                        titleColor: primaryColor,
                        bodyColor: textColor,
                        borderColor: gridColor,
                        borderWidth: 1,
                        padding: 12,
                        displayColors: true,
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${Number(context.parsed.y).toFixed(2)}%`,
                        },
                    },
                },
                scales: {
                    y: {
                        min: 0,
                        suggestedMax: suggestedMaximum,
                        ticks: { color: textColor, callback: (value) => `${value}%` },
                        grid: { color: gridColor, drawBorder: false },
                    },
                    x: {
                        ticks: { color: textColor, maxTicksLimit: 12 },
                        grid: { color: gridColor, drawBorder: false },
                    },
                },
            },
        })
        window[CHART_KEY].resize()
        return true
    }

    function schedule(root = document, retry = 0) {
        const panel = trendPanel(root)
        if (!panel?.querySelector('#utilizationTrendChart')) return
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (renderTrendChart(root)) return
                if (retry >= MAX_VISIBILITY_RETRIES) return
                window.setTimeout(() => schedule(root, retry + 1), 50)
            })
        })
    }

    const resizeObserver =
        typeof ResizeObserver === 'undefined'
            ? { observe() {}, unobserve() {} }
            : new ResizeObserver((entries) => {
                  const visibleEntry = entries.find(
                      (entry) => entry.contentRect.width > 0 && entry.contentRect.height > 0
                  )
                  if (!visibleEntry) return
                  if (window[CHART_KEY]) {
                      window[CHART_KEY].resize()
                  } else {
                      schedule(visibleEntry.target.closest('#utilization-trend-panel') || document)
                  }
              })

    document.addEventListener('DOMContentLoaded', () => schedule(document))
    document.addEventListener('kaori:analytics-tab-visible', (event) => {
        if (event.detail?.tabId === 'trend') schedule(event.target)
    })
    document.body?.addEventListener('htmx:load', (event) => schedule(event.detail?.elt || document))
    document.body?.addEventListener('htmx:afterSwap', (event) => schedule(event.detail?.target || document))
    document.body?.addEventListener('htmx:afterSettle', (event) => schedule(event.detail?.elt || document))
    window.addEventListener('resize', () => {
        if (window[CHART_KEY]) window[CHART_KEY].resize()
    })
})()
