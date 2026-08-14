;(() => {
    const chartKey = 'kaoriObjectStorageAnalyticsChart'

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

    function destroyChart() {
        if (!window[chartKey]) return
        window[chartKey].destroy()
        window[chartKey] = null
    }

    function render(root = document) {
        const panel =
            root.querySelector?.('[data-object-storage-trend-panel]') ||
            document.querySelector('[data-object-storage-trend-panel]')
        if (!panel || typeof Chart === 'undefined') return
        const canvas = panel.querySelector('[data-object-storage-chart]')
        if (!canvas) return
        let points
        try {
            points = JSON.parse(panel.dataset.objectStorageTrendPoints || '[]')
        } catch (error) {
            console.error('Unable to parse Object Storage Analytics trend data.', error)
            return
        }
        if (!Array.isArray(points) || !points.length) return
        destroyChart()
        const isPerformance = panel.dataset.objectStoragePageKey === 'performance'
        const textColor = cssVariable('--kaori-content-secondary', 'CanvasText')
        const gridColor = cssVariable('--kaori-outline-subtle', 'transparent')
        const primaryColor = cssVariable('--kaori-brand-primary', 'CanvasText')
        const labels = points.map((point) =>
            new Intl.DateTimeFormat([], {
                month: 'short',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
            }).format(new Date(Number(point.timestamp) * 1000))
        )
        window[chartKey] = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: isPerformance ? 'Request Rate' : 'Storage Usage',
                        data: points.map((point) => Number(point.value)),
                        borderColor: primaryColor,
                        backgroundColor: primaryColor,
                        borderWidth: 3,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        tension: 0.3,
                        fill: false,
                        spanGaps: true,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) =>
                                isPerformance
                                    ? `${Number(context.parsed.y).toFixed(2)}/s`
                                    : formatBytes(Number(context.parsed.y)),
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: { color: textColor, maxTicksLimit: 10 },
                        grid: { color: gridColor },
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: textColor,
                            callback: (value) => (isPerformance ? `${value}/s` : formatBytes(Number(value))),
                        },
                        grid: { color: gridColor },
                    },
                },
            },
        })
    }

    document.addEventListener('DOMContentLoaded', () => render(document))
    document.body.addEventListener('htmx:afterSwap', (event) => render(event.target))
    document.body.addEventListener('htmx:beforeSwap', destroyChart)
})()
