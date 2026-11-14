;(() => {
    const charts = new Map()
    const panelSelector = '[data-registry-capacity-quota-series]'

    const cssVariable = (name, fallback) =>
        getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback

    const formatBytes = (value) => {
        if (!Number.isFinite(value)) return 'N/A'
        const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
        let amount = value
        let index = 0
        while (Math.abs(amount) >= 1024 && index < units.length - 1) {
            amount /= 1024
            index += 1
        }
        return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
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
        const panels = root.matches?.(panelSelector) ? [root] : Array.from(root.querySelectorAll?.(panelSelector) || [])

        panels.forEach((panel) => {
            const canvas = panel.querySelector('[data-registry-capacity-quota-chart]')
            if (!canvas || charts.has(canvas)) return

            let rows
            try {
                rows = JSON.parse(panel.dataset.registryCapacityQuotaSeries || '[]')
            } catch {
                return
            }
            if (!Array.isArray(rows) || !rows.length) return

            const data = rows.slice(0, 5)
            const textColor = cssVariable('--kaori-content-secondary', 'CanvasText')
            const gridColor = cssVariable('--kaori-outline-subtle', 'transparent')
            const normalColor = cssVariable('--kaori-brand-primary', 'CanvasText')
            const warningColor = cssVariable('--kaori-status-warning', normalColor)
            const values = data.map((row) => Number(row.utilization_percent))
            const maxObserved = Math.max(...values)
            let axisMax = 100
            if (maxObserved <= 1) axisMax = 1
            else if (maxObserved <= 5) axisMax = 5
            else if (maxObserved <= 25) axisMax = 25
            else if (maxObserved > 100) axisMax = Math.ceil(maxObserved / 25) * 25

            const axisNote = panel.querySelector('[data-registry-capacity-axis-note]')
            if (axisNote) {
                axisNote.textContent = `0–${axisMax}% axis${axisMax < 100 ? ' · zoomed for readability' : ''}`
            }

            const chart = new Chart(canvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: data.map((row) =>
                        row.project_name.length > 19 ? `${row.project_name.slice(0, 18)}…` : row.project_name
                    ),
                    datasets: [
                        {
                            label: 'Quota used',
                            data: values,
                            backgroundColor: values.map((value) => (value > 100 ? warningColor : normalColor)),
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
                                    const used = formatBytes(Number(row.usage_bytes))
                                    const quota = formatBytes(Number(row.quota_bytes))
                                    const percent = Number(row.utilization_percent).toFixed(1)
                                    return `${percent}% used · ${used} / ${quota}`
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            min: 0,
                            max: axisMax,
                            ticks: {
                                color: textColor,
                                callback: (value) => `${value}%`,
                            },
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
