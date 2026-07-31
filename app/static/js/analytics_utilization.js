(() => {
    const CHART_KEY = 'kaoriUtilizationTrendChart';

    const cssVariable = (name, fallback) => (
        getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    );

    function trendPanel(root = document) {
        if (root?.id === 'utilization-trend-panel') return root;
        return root?.querySelector?.('#utilization-trend-panel') || document.getElementById('utilization-trend-panel');
    }

    function parseTrendData(panel) {
        const source = panel?.querySelector('[data-utilization-trend-data]');
        if (!source) return null;
        try {
            return JSON.parse(source.textContent || '{}');
        } catch (error) {
            console.error('Unable to parse utilization trend data.', error);
            return null;
        }
    }

    function destroyChart() {
        if (window[CHART_KEY]) {
            window[CHART_KEY].destroy();
            window[CHART_KEY] = null;
        }
    }

    function renderTrendChart(root = document) {
        const panel = trendPanel(root);
        const canvas = panel?.querySelector('#utilizationTrendChart');
        const data = parseTrendData(panel);
        if (!panel || !canvas || !data || typeof Chart === 'undefined') return;

        const cpuTrend = Array.isArray(data.cpu) ? data.cpu : [];
        const memoryTrend = Array.isArray(data.memory) ? data.memory : [];
        const podTrend = Array.isArray(data.pods) ? data.pods : [];
        const emptyState = panel.querySelector('#trendEmptyState');
        const chartContainer = panel.querySelector('#utilizationTrendChartContainer');

        if (!cpuTrend.length && !memoryTrend.length && !podTrend.length) {
            destroyChart();
            chartContainer?.classList.add('hidden');
            emptyState?.classList.remove('hidden');
            return;
        }

        chartContainer?.classList.remove('hidden');
        emptyState?.classList.add('hidden');
        destroyChart();

        const parentWidth = Math.max(canvas.parentElement?.clientWidth || 1200, 600);
        const parentHeight = Math.max(canvas.parentElement?.clientHeight || 320, 260);
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        canvas.style.width = '100%';
        canvas.style.height = `${parentHeight}px`;
        canvas.width = Math.floor(parentWidth * ratio);
        canvas.height = Math.floor(parentHeight * ratio);

        const cardColor = cssVariable('--kaori-surface-card', 'Canvas');
        const textColor = cssVariable('--kaori-content-secondary', 'CanvasText');
        const primaryColor = cssVariable('--kaori-content-primary', 'CanvasText');
        const gridColor = cssVariable('--kaori-outline-subtle', 'transparent');
        const series = [
            ['CPU', cpuTrend, cssVariable('--kaori-brand-primary', 'CanvasText')],
            ['Memory', memoryTrend, cssVariable('--kaori-status-normal', 'CanvasText')],
            ['Pods', podTrend, cssVariable('--kaori-status-pending', 'CanvasText')],
        ];
        const baseTrend = series.find(([, values]) => values.length)?.[1] || [];
        const labels = baseTrend.map((item) => new Date(item.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));

        window[CHART_KEY] = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels,
                datasets: series.map(([label, values, color]) => ({
                    label,
                    data: values.map((item) => item.value),
                    borderColor: color,
                    backgroundColor: color,
                    pointBackgroundColor: color,
                    pointBorderColor: cardColor,
                    pointBorderWidth: 2,
                    pointRadius: 2.5,
                    pointHoverRadius: 5,
                    borderWidth: 3,
                    fill: false,
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
                        callbacks: { label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%` },
                    },
                },
                scales: {
                    y: { min: 0, max: 100, ticks: { color: textColor, callback: (value) => `${value}%` }, grid: { color: gridColor, drawBorder: false } },
                    x: { ticks: { color: textColor, maxTicksLimit: 12 }, grid: { color: gridColor, drawBorder: false } },
                },
            },
        });
        window.setTimeout(() => window[CHART_KEY]?.resize(), 80);
    }

    function schedule(root = document) {
        requestAnimationFrame(() => requestAnimationFrame(() => renderTrendChart(root)));
    }

    document.addEventListener('DOMContentLoaded', () => schedule(document));
    document.body.addEventListener('htmx:afterSwap', (event) => schedule(event.detail?.target || document));
    window.addEventListener('resize', () => window[CHART_KEY]?.resize());
})();
