;(() => {
    const chartKey = 'kaoriObjectStorageAnalyticsChart'
    const bucketForecastChartKey = 'kaoriObjectStorageBucketForecastChart'

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

    const parsePoints = (raw) => {
        try {
            const value = JSON.parse(raw || '[]')
            return Array.isArray(value) ? value : []
        } catch (error) {
            console.error('Unable to parse Object Storage Analytics trend data.', error)
            return []
        }
    }

    function destroyChart() {
        if (!window[chartKey]) return
        window[chartKey].destroy()
        window[chartKey] = null
    }

    function destroyBucketForecastChart() {
        if (!window[bucketForecastChartKey]) return
        window[bucketForecastChartKey].destroy()
        window[bucketForecastChartKey] = null
    }

    function render(root = document) {
        const panel =
            root.querySelector?.('[data-object-storage-trend-panel]') ||
            document.querySelector('[data-object-storage-trend-panel]')
        if (!panel || typeof Chart === 'undefined') return
        const canvas = panel.querySelector('[data-object-storage-chart]')
        if (!canvas) return

        const points = parsePoints(panel.dataset.objectStorageTrendPoints)
        const secondaryPoints = parsePoints(panel.dataset.objectStorageSecondaryTrendPoints)
        const projectionPoints = parsePoints(panel.dataset.objectStorageProjectionPoints)
        if (!points.length) return

        destroyChart()
        const mode = panel.dataset.objectStorageChartMode || panel.dataset.objectStoragePageKey || 'usage'
        const isPerformance = mode === 'performance'
        const isForecast = mode === 'forecast'
        const textColor = cssVariable('--kaori-content-secondary', 'CanvasText')
        const gridColor = cssVariable('--kaori-outline-subtle', 'transparent')
        const primaryColor = cssVariable('--kaori-brand-primary', 'CanvasText')
        const secondaryColor = cssVariable('--kaori-status-critical', 'CanvasText')
        const labels = points.map((point) =>
            new Intl.DateTimeFormat([], {
                month: 'short',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
            }).format(new Date(Number(point.timestamp) * 1000))
        )
        const datasets = [
            {
                label: isPerformance ? 'Request Rate' : isForecast ? 'Observed Usage' : 'Storage Usage',
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
        ]
        if (isPerformance && secondaryPoints.length) {
            const secondaryByTimestamp = new Map(
                secondaryPoints.map((point) => [Number(point.timestamp), Number(point.value)])
            )
            datasets.push({
                label: 'Error Rate',
                data: points.map((point) => secondaryByTimestamp.get(Number(point.timestamp)) ?? null),
                borderColor: secondaryColor,
                backgroundColor: secondaryColor,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderDash: [5, 4],
                tension: 0.3,
                fill: false,
                spanGaps: true,
            })
        }
        if (isForecast && projectionPoints.length) {
            const combinedLabels = [...points, ...projectionPoints.slice(1)].map((point) =>
                new Intl.DateTimeFormat([], {
                    month: 'short',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                }).format(new Date(Number(point.timestamp) * 1000))
            )
            labels.splice(0, labels.length, ...combinedLabels)
            datasets[0].data = [
                ...points.map((point) => Number(point.value)),
                ...projectionPoints.slice(1).map(() => null),
            ]
            datasets.push({
                label: '30d Linear Projection',
                data: [...points.slice(0, -1).map(() => null), ...projectionPoints.map((point) => Number(point.value))],
                borderColor: primaryColor,
                backgroundColor: primaryColor,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderDash: [6, 5],
                tension: 0,
                fill: false,
                spanGaps: true,
            })
        }
        window[chartKey] = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        display: (isPerformance || isForecast) && datasets.length > 1,
                        labels: { color: textColor },
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) =>
                                isPerformance
                                    ? `${context.dataset.label}: ${Number(context.parsed.y).toFixed(2)}/s`
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

    function renderBucketForecastChart(root = document) {
        const panel =
            root.querySelector?.('[data-object-storage-bucket-forecast-chart-panel]') ||
            document.querySelector('[data-object-storage-bucket-forecast-chart-panel]')
        if (!panel || typeof Chart === 'undefined') return
        const canvas = panel.querySelector('[data-object-storage-bucket-forecast-chart]')
        if (!canvas) return

        const rows = parsePoints(panel.dataset.objectStorageBucketForecastRows)
            .filter(
                (row) =>
                    row?.history_state === 'ready' &&
                    row.current_bytes !== null &&
                    row.current_bytes !== undefined &&
                    row.projected_30d !== null &&
                    row.projected_30d !== undefined &&
                    Number.isFinite(Number(row.current_bytes)) &&
                    Number.isFinite(Number(row.projected_30d))
            )
            .sort(
                (left, right) =>
                    Number(right.projected_30d ?? right.current_bytes ?? 0) -
                    Number(left.projected_30d ?? left.current_bytes ?? 0)
            )
            .slice(0, 8)
        if (!rows.length) return

        destroyBucketForecastChart()
        const textColor = cssVariable('--kaori-content-secondary', 'CanvasText')
        const gridColor = cssVariable('--kaori-outline-subtle', 'transparent')
        const primaryColor = cssVariable('--kaori-brand-primary', 'CanvasText')
        const accentColor = cssVariable('--kaori-brand-accent', primaryColor)

        window[bucketForecastChartKey] = new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: rows.map((row) => String(row.name || 'Unnamed Bucket')),
                datasets: [
                    {
                        label: 'Current Usage',
                        data: rows.map((row) => Number(row.current_bytes)),
                        backgroundColor: accentColor,
                        borderColor: accentColor,
                        borderWidth: 1,
                        borderRadius: 4,
                        maxBarThickness: 18,
                    },
                    {
                        label: 'Projected 30d',
                        data: rows.map((row) => Number(row.projected_30d)),
                        backgroundColor: primaryColor,
                        borderColor: primaryColor,
                        borderWidth: 1,
                        borderRadius: 4,
                        maxBarThickness: 18,
                    },
                ],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: true, labels: { color: textColor } },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${formatBytes(Number(context.parsed.x))}`,
                        },
                    },
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { color: textColor, callback: (value) => formatBytes(Number(value)) },
                        grid: { color: gridColor },
                    },
                    y: {
                        ticks: { color: textColor, autoSkip: false },
                        grid: { display: false },
                    },
                },
            },
        })
    }

    function renderAll(root = document) {
        render(root)
        renderBucketForecastChart(root)
    }

    function destroyAllCharts() {
        destroyChart()
        destroyBucketForecastChart()
    }

    document.addEventListener('DOMContentLoaded', () => renderAll(document))
    document.addEventListener('kaori:analytics-tab-visible', (event) => renderAll(event.target))
    document.body.addEventListener('htmx:afterSwap', (event) => renderAll(event.target))
    document.body.addEventListener('htmx:beforeSwap', destroyAllCharts)
})()
