(() => {
    const CHART_KEY = 'kaoriUtilizationTrendChart';
    const MAX_VISIBILITY_RETRIES = 12;
    let observedContainer = null;

    const cssVariable = (name, fallback) => (
        getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
    );

    function trendPanel(root = document) {
        if (root?.id === 'utilization-trend-panel' && root.isConnected) return root;
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

    function chartContainer(panel) {
        return panel?.querySelector('#utilizationTrendChartContainer') || null;
    }

    function isTrendRenderable(panel, container) {
        if (!panel?.isConnected || !container?.isConnected || panel.hidden) return false;
        const panelStyle = window.getComputedStyle(panel);
        const containerStyle = window.getComputedStyle(container);
        if (panelStyle.display === 'none' || panelStyle.visibility === 'hidden') return false;
        if (containerStyle.display === 'none' || containerStyle.visibility === 'hidden') return false;
        const bounds = container.getBoundingClientRect();
        return bounds.width > 0 && bounds.height > 0;
    }

    function observeContainer(container) {
        if (typeof ResizeObserver === 'undefined' || !container || observedContainer === container) return;

        if (observedContainer) resizeObserver.unobserve(observedContainer);
        observedContainer = container;
        resizeObserver.observe(container);
    }

    function renderTrendChart(root = document) {
        const panel = trendPanel(root);
        const canvas = panel?.querySelector('#utilizationTrendChart');
        const container = chartContainer(panel);
        const data = parseTrendData(panel);
        if (!panel || !canvas || !container || !data || typeof Chart === 'undefined') return false;

        observeContainer(container);
        if (!isTrendRenderable(panel, container)) return false;

        const cpuTrend = Array.isArray(data.cpu) ? data.cpu : [];
        const memoryTrend = Array.isArray(data.memory) ? data.memory : [];
        const podTrend = Array.isArray(data.pods) ? data.pods : [];
        const emptyState = panel.querySelector('#trendEmptyState');

        if (!cpuTrend.length && !memoryTrend.length && !podTrend.length) {
            destroyChart();
            container.classList.add('hidden');
            emptyState?.classList.remove('hidden');
            return true;
        }

        container.classList.remove('hidden');
        emptyState?.classList.add('hidden');
        destroyChart();

        canvas.style.width = '100%';
        canvas.style.height = '100%';

        const ratio = Math.min(window.devicePixelRatio || 1, 2);
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
        const labels = baseTrend.map((item) => new Date(item.timestamp * 1000).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
        }));

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
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%`,
                        },
                    },
                },
                scales: {
                    y: {
                        min: 0,
                        max: 100,
                        ticks: { color: textColor, callback: (value) => `${value}%` },
                        grid: { color: gridColor, drawBorder: false },
                    },
                    x: {
                        ticks: { color: textColor, maxTicksLimit: 12 },
                        grid: { color: gridColor, drawBorder: false },
                    },
                },
            },
        });
        window[CHART_KEY].resize();
        return true;
    }

    function schedule(root = document, retry = 0) {
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (renderTrendChart(root)) return;
                if (retry >= MAX_VISIBILITY_RETRIES) return;
                window.setTimeout(() => schedule(root, retry + 1), 50);
            });
        });
    }

    const resizeObserver = typeof ResizeObserver === 'undefined'
        ? { observe() {}, unobserve() {} }
        : new ResizeObserver((entries) => {
            const visibleEntry = entries.find((entry) => entry.contentRect.width > 0 && entry.contentRect.height > 0);
            if (!visibleEntry) return;
            if (window[CHART_KEY]) {
                window[CHART_KEY].resize();
            } else {
                schedule(visibleEntry.target.closest('#utilization-trend-panel') || document);
            }
        });

    document.addEventListener('DOMContentLoaded', () => schedule(document));
    document.addEventListener('kaori:analytics-tab-visible', (event) => {
        if (event.detail?.tabId === 'trend') schedule(event.target);
    });
    document.body?.addEventListener('htmx:load', (event) => schedule(event.detail?.elt || document));
    document.body?.addEventListener('htmx:afterSwap', (event) => schedule(event.detail?.target || document));
    document.body?.addEventListener('htmx:afterSettle', (event) => schedule(event.detail?.elt || document));
    window.addEventListener('resize', () => {
        if (window[CHART_KEY]) window[CHART_KEY].resize();
    });
})();
