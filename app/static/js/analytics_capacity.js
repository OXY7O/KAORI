(() => {
    function cssVariable(name, fallback) {
        const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return value || fallback;
    }

    function readPayload() {
        const element = document.getElementById('capacity-allocation-chart-data');
        if (!element) return null;
        try {
            return JSON.parse(element.textContent || '{}');
        } catch {
            return null;
        }
    }

    function renderCapacityAllocationChart() {
        const canvas = document.getElementById('capacity-allocation-chart');
        const payload = readPayload();
        if (!canvas || !payload || typeof Chart === 'undefined') return;

        const existing = Chart.getChart(canvas);
        if (existing) existing.destroy();

        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: payload.labels || [],
                datasets: [{
                    data: payload.values || [],
                    backgroundColor: [
                        cssVariable('--kaori-brand-primary', 'CanvasText'),
                        cssVariable('--kaori-status-maintenance', 'CanvasText'),
                        cssVariable('--kaori-status-info', 'CanvasText'),
                        cssVariable('--kaori-status-warning', 'CanvasText'),
                    ],
                    borderColor: cssVariable('--kaori-surface-card', 'Canvas'),
                    borderWidth: 3,
                    hoverOffset: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '62%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            boxWidth: 8,
                            color: cssVariable('--kaori-content-secondary', 'CanvasText'),
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label(context) {
                                return `${context.label}: ${Number(context.raw || 0).toFixed(1)}% used`;
                            },
                        },
                    },
                },
            },
        });
    }

    document.addEventListener('DOMContentLoaded', renderCapacityAllocationChart);
    document.body.addEventListener('htmx:afterSwap', renderCapacityAllocationChart);
    document.body.addEventListener('htmx:afterSettle', renderCapacityAllocationChart);
})();
