;(() => {
    const charts = new Map()
    const panelSelector = '[data-registry-growth-chart-panel]'

    const cssVariable = (name, fallback) =>
        getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback

    const formatBytes = (value) => {
        if (!Number.isFinite(value)) return 'N/A'
        const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
        let size = value
        let index = 0
        while (Math.abs(size) >= 1024 && index < units.length - 1) {
            size /= 1024
            index += 1
        }
        return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
    }

    const formatTime = (unix) =>
        new Intl.DateTimeFormat([], {
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        }).format(new Date(Number(unix) * 1000))

    function pointRadiusForSeries(source) {
        if (source.mode === 'checkpoints') return 4
        return source.points.length <= 6 ? 3 : 0
    }

    function destroyRemovedCharts(target) {
        for (const [canvas, chart] of charts.entries()) {
            if (!canvas.isConnected || (target && (target === canvas || target.contains?.(canvas)))) {
                chart.destroy()
                charts.delete(canvas)
            }
        }
    }

    function render(root = document) {
        if (typeof Chart === 'undefined') return
        const candidates = root.matches?.(panelSelector)
            ? [root]
            : Array.from(root.querySelectorAll?.(panelSelector) || [])

        candidates.forEach((panel) => {
            const canvas = panel.querySelector('[data-registry-growth-chart]')
            if (!canvas || charts.has(canvas)) return

            let series
            try {
                series = JSON.parse(panel.dataset.registryGrowthChartSeries || '[]')
            } catch {
                return
            }
            if (!Array.isArray(series) || !series.length) return

            const textColor = cssVariable('--kaori-content-secondary', 'CanvasText')
            const gridColor = cssVariable('--kaori-outline-subtle', 'transparent')
            const palette = [
                cssVariable('--kaori-brand-primary', 'CanvasText'),
                cssVariable('--kaori-status-info', 'CanvasText'),
                cssVariable('--kaori-status-normal', 'CanvasText'),
            ]
            const isStorage = panel.dataset.registryGrowthChartPanel === 'storage'
            const datasets = series.slice(0, 3).map((source, index) => ({
                label: source.label,
                data: (source.points || []).map((point) => ({
                    x: Number(point.timestamp),
                    y: Number(point.value),
                })),
                borderColor: palette[index],
                backgroundColor: palette[index],
                borderWidth: 2.5,
                borderDash: source.mode === 'checkpoints' ? [6, 4] : [],
                pointRadius: pointRadiusForSeries(source),
                pointHoverRadius: 5,
                fill: false,
                spanGaps: false,
                tension: 0,
                parsing: false,
            }))

            const chart = new Chart(canvas.getContext('2d'), {
                type: 'line',
                data: { datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    interaction: { mode: 'nearest', intersect: false },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'bottom',
                            labels: { color: textColor },
                        },
                        tooltip: {
                            callbacks: {
                                title: (items) => formatTime(items[0]?.parsed.x),
                                label: (context) => {
                                    const value = Number(context.parsed.y)
                                    const formatted = isStorage ? formatBytes(value) : value.toLocaleString()
                                    return `${context.dataset.label}: ${formatted}`
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            ticks: {
                                color: textColor,
                                maxTicksLimit: 3,
                                maxRotation: 0,
                                minRotation: 0,
                                callback: (value) => formatTime(value),
                            },
                            grid: { color: gridColor },
                        },
                        y: {
                            beginAtZero: false,
                            ticks: {
                                color: textColor,
                                callback: (value) =>
                                    isStorage ? formatBytes(Number(value)) : Number(value).toLocaleString(),
                            },
                            grid: { color: gridColor },
                        },
                    },
                },
            })
            charts.set(canvas, chart)
        })
        destroyRemovedCharts()
    }

    document.addEventListener('DOMContentLoaded', () => render())
    document.addEventListener('kaori:analytics-tab-visible', (event) => render(event.target))
    document.body.addEventListener('htmx:beforeSwap', (event) => destroyRemovedCharts(event.detail.target))
    document.body.addEventListener('htmx:afterSwap', (event) => render(event.detail.target || document))
    document.body.addEventListener('htmx:afterSettle', (event) => render(event.detail.elt || document))
})()
