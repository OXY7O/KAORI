;(() => {
    const charts = new Map()
    const observers = new Map()
    const MAX_RETRIES = 12

    function cssToken(name, fallback) {
        const value = window.getComputedStyle(document.documentElement).getPropertyValue(name).trim()
        return value || fallback
    }

    function palette() {
        return {
            cpu: cssToken('--kaori-status-info', 'rgb(37 99 235)'),
            memory: cssToken('--kaori-brand-primary', 'rgb(124 58 237)'),
            storage: cssToken('--kaori-status-normal', 'rgb(5 150 105)'),
            pods: cssToken('--kaori-status-warning', 'rgb(217 119 6)'),
            warning: cssToken('--kaori-status-warning', 'rgb(217 119 6)'),
            critical: cssToken('--kaori-status-critical', 'rgb(220 38 38)'),
            grid: cssToken('--kaori-outline-subtle', 'rgb(238 234 244)'),
            text: cssToken('--kaori-content-muted', 'rgb(111 104 122)'),
        }
    }

    function parsePayload(id) {
        const node = document.getElementById(id)
        if (!node) return null
        try {
            const content = node.content?.textContent ?? node.textContent ?? '{}'
            return JSON.parse(content)
        } catch {
            return null
        }
    }

    function isMeasurable(canvas) {
        if (!canvas?.isConnected || canvas.hidden) return false
        const panel = canvas.closest('[data-analytics-tab-panel]')
        if (panel?.hidden || window.getComputedStyle(panel).display === 'none') return false
        const container = canvas.closest('[data-kaori-forecast-chart-container]')
        if (!container) return false
        const rect = container.getBoundingClientRect()
        return rect.width > 0 && rect.height > 0
    }

    function destroy(canvas) {
        const chart = charts.get(canvas)
        if (chart) chart.destroy()
        charts.delete(canvas)
        const observer = observers.get(canvas)
        if (observer) observer.disconnect()
        observers.delete(canvas)
    }

    function thresholdDataset(label, value, labels, color, dash) {
        return {
            label,
            data: Array(labels.length).fill(Number(value)),
            borderColor: color,
            backgroundColor: color,
            borderWidth: 1.5,
            borderDash: dash,
            pointRadius: 0,
            pointHoverRadius: 0,
            tension: 0,
            fill: false,
        }
    }

    function resourceDataset(payload, key) {
        return payload?.datasets?.find((dataset) => dataset.key === key) || null
    }

    function resourceSeries(dataset, colors) {
        const color = colors[dataset.key] || colors.cpu
        return [
            {
                label: `${dataset.label} Historical`,
                data: dataset.historical,
                borderColor: color,
                backgroundColor: color,
                borderWidth: 2.5,
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 3,
                fill: false,
                spanGaps: false,
            },
            {
                label: `${dataset.label} Projection`,
                data: dataset.forecast,
                borderColor: color,
                backgroundColor: color,
                borderWidth: 2.5,
                borderDash: [8, 6],
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 3,
                fill: false,
                spanGaps: false,
            },
        ]
    }

    function chartOptions(colors, maxTicks = 9, suggestedMax = 100) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label(context) {
                            const value = context.parsed.y
                            if (value === null || value === undefined) return null
                            return `${context.dataset.label}: ${Number(value).toFixed(2)}%`
                        },
                    },
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    suggestedMax,
                    grid: { color: colors.grid, drawBorder: false },
                    ticks: {
                        color: colors.text,
                        callback(value) {
                            return `${value}%`
                        },
                    },
                },
                x: {
                    grid: { display: false, drawBorder: false },
                    ticks: { color: colors.text, maxRotation: 0, autoSkip: true, maxTicksLimit: maxTicks },
                },
            },
        }
    }

    function buildConfig(canvas, payload) {
        const colors = palette()
        const mode = canvas.dataset.chartMode || 'resource'
        let labels = []
        let datasets = []

        if (mode === 'combined') {
            const available = Array.isArray(payload?.datasets) ? payload.datasets : []
            if (!available.length) return null
            labels = payload?.labels || available[0].labels || []
            available.forEach((dataset) => datasets.push(...resourceSeries(dataset, colors)))
        } else {
            const dataset = resourceDataset(payload, canvas.dataset.resourceKey || '')
            if (!dataset) return null
            labels = dataset.labels || []
            datasets = resourceSeries(dataset, colors)
        }

        datasets.push(
            thresholdDataset(
                `Warning ${payload.warning_threshold}%`,
                payload.warning_threshold,
                labels,
                colors.warning,
                [5, 5]
            ),
            thresholdDataset(
                `Critical ${payload.critical_threshold}%`,
                payload.critical_threshold,
                labels,
                colors.critical,
                [2, 4]
            )
        )

        const observedMaximum = datasets.reduce(
            (maximum, dataset) => {
                const values = Array.isArray(dataset.data) ? dataset.data : []
                return values.reduce((current, value) => {
                    const numeric = Number(value)
                    return Number.isFinite(numeric) ? Math.max(current, numeric) : current
                }, maximum)
            },
            Number(payload?.critical_threshold) || 100
        )
        const suggestedMax = Math.max(100, Math.ceil(observedMaximum / 10) * 10)

        return {
            type: 'line',
            data: { labels, datasets },
            options: chartOptions(colors, mode === 'combined' ? 10 : 8, suggestedMax),
        }
    }

    function render(canvas) {
        if (typeof window.Chart === 'undefined' || !isMeasurable(canvas)) return false
        const payload = parsePayload(canvas.dataset.chartDataId || 'forecast-chart-data')
        const config = buildConfig(canvas, payload)
        if (!config) {
            destroy(canvas)
            return false
        }
        destroy(canvas)
        charts.set(canvas, new window.Chart(canvas, config))
        const container = canvas.closest('[data-kaori-forecast-chart-container]')
        if (window.ResizeObserver && container) {
            const observer = new ResizeObserver(() => {
                const chart = charts.get(canvas)
                if (chart && isMeasurable(canvas)) chart.resize()
            })
            observer.observe(container)
            observers.set(canvas, observer)
        }
        return true
    }

    function schedule(canvas, attempt = 0) {
        if (!canvas?.isConnected) return
        window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
                if (render(canvas) || attempt >= MAX_RETRIES) return
                window.setTimeout(() => schedule(canvas, attempt + 1), 60)
            })
        })
    }

    function hydrate(root = document) {
        const connected = root?.isConnected === false ? document : root
        connected.querySelectorAll?.('[data-kaori-forecast-chart]').forEach((canvas) => schedule(canvas))
        if (connected.matches?.('[data-kaori-forecast-chart]')) schedule(connected)
        for (const canvas of charts.keys()) {
            if (!canvas.isConnected) destroy(canvas)
        }
    }

    document.addEventListener('DOMContentLoaded', () => hydrate(document))
    document.addEventListener('kaori:analytics-tab-visible', (event) => hydrate(event.target))
    document.body.addEventListener('htmx:load', (event) => hydrate(event.detail?.elt || event.target))
    document.body.addEventListener('htmx:afterSwap', (event) => hydrate(event.detail?.target || document))
    document.body.addEventListener('htmx:afterSettle', (event) => hydrate(event.detail?.target || document))
    window.addEventListener('resize', () => {
        for (const [canvas, chart] of charts.entries()) {
            if (isMeasurable(canvas)) chart.resize()
        }
    })
})()
