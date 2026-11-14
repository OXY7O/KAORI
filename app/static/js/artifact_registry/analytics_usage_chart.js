;(() => {
    const charts = new Map()
    const panelSelector = '[data-registry-usage-series]'

    const cssVariable = (name, fallback) =>
        getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback

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
        const panels = root.matches?.(panelSelector) ? [root] : Array.from(root.querySelectorAll?.(panelSelector) || [])

        panels.forEach((panel) => {
            const canvas = panel.querySelector('[data-registry-usage-chart]')
            if (!canvas || charts.has(canvas)) return

            let rows
            try {
                rows = JSON.parse(panel.dataset.registryUsageSeries || '[]')
            } catch {
                return
            }
            if (!Array.isArray(rows)) return
            const data = rows
                .filter((row) => Number.isFinite(row.pull_count) && row.pull_count >= 0)
                .slice(0, 5)
            if (!data.length) return

            const textColor = cssVariable('--kaori-content-secondary', 'CanvasText')
            const gridColor = cssVariable('--kaori-outline-subtle', 'transparent')
            const brandColor = cssVariable('--kaori-brand-primary', 'CanvasText')
            const values = data.map((row) => row.pull_count)
            const maximum = Math.max(...values)
            const axisMax = maximum === 0 ? 1 : Math.ceil(maximum / 5) * 5

            const chart = new Chart(canvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: data.map((row) =>
                        row.project_name.length > 19 ? `${row.project_name.slice(0, 18)}…` : row.project_name
                    ),
                    datasets: [
                        {
                            label: 'Observed pulls',
                            data: values,
                            backgroundColor: brandColor,
                            borderRadius: 4,
                            maxBarThickness: 28,
                        },
                    ],
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (items) => {
                                    const row = data[items[0]?.dataIndex]
                                    return row ? `${row.project_name} · ${row.registry_name}` : ''
                                },
                                label: (context) => {
                                    const row = data[context.dataIndex]
                                    if (!row) return 'Evidence unavailable'
                                    return `${row.pull_count.toLocaleString()} observed pulls`
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            min: 0,
                            max: axisMax,
                            ticks: { color: textColor, precision: 0 },
                            grid: { color: gridColor },
                        },
                        y: {
                            ticks: { color: textColor },
                            grid: { display: false },
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
