const forecastCharts = new Map();

const FORECAST_SERIES_COLORS = {
    cpu: '#7C3AED',
    memory: '#2563EB',
    storage: '#16A34A',
    pods: '#D97706',
    warning: '#F59E0B',
    critical: '#DC2626'
};

function safeParseForecastJson(elementId) {
    const element = document.getElementById(elementId);

    if (!element) {
        return null;
    }

    try {
        return JSON.parse(element.textContent);
    } catch {
        return null;
    }
}

function isVisibleElement(element) {
    return Boolean(element && (element.offsetWidth || element.offsetHeight || element.getClientRects().length));
}

function getResourceDataset(payload, resourceKey) {
    if (!payload || !Array.isArray(payload.datasets)) {
        return null;
    }

    return payload.datasets.find((dataset) => dataset.key === resourceKey) || null;
}

function destroyForecastChart(canvasId) {
    const chart = forecastCharts.get(canvasId);

    if (chart) {
        chart.destroy();
        forecastCharts.delete(canvasId);
    }
}

function buildThresholdDataset({ label, value, labels, color, dash }) {
    return {
        label,
        data: Array(labels.length).fill(value),
        borderColor: color,
        backgroundColor: color,
        borderWidth: 1.5,
        borderDash: dash,
        pointRadius: 0,
        pointHoverRadius: 0,
        tension: 0,
        fill: false
    };
}

function renderResourceForecastCharts() {
    if (typeof Chart === 'undefined') {
        return;
    }

    const payload = safeParseForecastJson('forecast-trend-chart-data');

    document.querySelectorAll('[data-forecast-resource-canvas="true"]').forEach((canvas) => {
        if (!isVisibleElement(canvas)) {
            return;
        }

        const resourceKey = canvas.dataset.forecastResourceKey;
        const dataset = getResourceDataset(payload, resourceKey);

        if (!dataset) {
            destroyForecastChart(canvas.id);
            return;
        }

        destroyForecastChart(canvas.id);

        const color = FORECAST_SERIES_COLORS[resourceKey] || FORECAST_SERIES_COLORS.cpu;
        const warningThreshold = Number(payload.warning_threshold || 75);
        const criticalThreshold = Number(payload.critical_threshold || 90);

        const chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: dataset.labels,
                datasets: [
                    {
                        label: `${dataset.label} Historical`,
                        data: dataset.historical,
                        borderColor: color,
                        backgroundColor: color,
                        borderWidth: 2.5,
                        tension: 0.35,
                        pointRadius: 0,
                        pointHoverRadius: 3,
                        fill: false
                    },
                    {
                        label: `${dataset.label} Forecast`,
                        data: dataset.forecast,
                        borderColor: color,
                        backgroundColor: color,
                        borderWidth: 2.5,
                        borderDash: [8, 6],
                        tension: 0.35,
                        pointRadius: 0,
                        pointHoverRadius: 3,
                        fill: false
                    },
                    buildThresholdDataset({
                        label: `Warning ${warningThreshold}%`,
                        value: warningThreshold,
                        labels: dataset.labels,
                        color: FORECAST_SERIES_COLORS.warning,
                        dash: [5, 5]
                    }),
                    buildThresholdDataset({
                        label: `Critical ${criticalThreshold}%`,
                        value: criticalThreshold,
                        labels: dataset.labels,
                        color: FORECAST_SERIES_COLORS.critical,
                        dash: [2, 4]
                    })
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            boxWidth: 8,
                            padding: 18
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label(context) {
                                const value = context.parsed.y;

                                if (value === null || value === undefined) {
                                    return null;
                                }

                                return `${context.dataset.label}: ${value.toFixed(2)}%`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        suggestedMax: 100,
                        grid: {
                            drawBorder: false
                        },
                        ticks: {
                            callback(value) {
                                return `${value}%`;
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false,
                            drawBorder: false
                        },
                        ticks: {
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 8
                        }
                    }
                }
            }
        });

        forecastCharts.set(canvas.id, chart);
    });
}

function buildTrendDatasets(payload) {
    const datasets = [];

    payload.datasets.forEach((item) => {
        const color = FORECAST_SERIES_COLORS[item.key] || FORECAST_SERIES_COLORS.cpu;

        datasets.push({
            label: `${item.label} Historical`,
            data: item.historical,
            borderColor: color,
            backgroundColor: color,
            borderWidth: 2.25,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 3,
            fill: false
        });

        datasets.push({
            label: `${item.label} Forecast`,
            data: item.forecast,
            borderColor: color,
            backgroundColor: color,
            borderWidth: 2.25,
            borderDash: [8, 6],
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 3,
            fill: false
        });
    });

    if (Array.isArray(payload.datasets) && payload.datasets.length > 0) {
        const labelsLength = payload.datasets[0].labels.length;

        datasets.push(buildThresholdDataset({
            label: `Warning ${payload.warning_threshold}%`,
            value: payload.warning_threshold,
            labels: Array(labelsLength),
            color: FORECAST_SERIES_COLORS.warning,
            dash: [5, 5]
        }));

        datasets.push(buildThresholdDataset({
            label: `Critical ${payload.critical_threshold}%`,
            value: payload.critical_threshold,
            labels: Array(labelsLength),
            color: FORECAST_SERIES_COLORS.critical,
            dash: [2, 4]
        }));
    }

    return datasets;
}

function renderTrendForecastChart() {
    if (typeof Chart === 'undefined') {
        return;
    }

    const canvas = document.getElementById('forecast-trend-chart');

    if (!canvas || !isVisibleElement(canvas)) {
        return;
    }

    const payload = safeParseForecastJson('forecast-trend-chart-data');

    if (!payload || !Array.isArray(payload.datasets) || payload.datasets.length === 0) {
        destroyForecastChart('forecast-trend-chart');
        return;
    }

    destroyForecastChart('forecast-trend-chart');

    const chart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: payload.datasets[0].labels,
            datasets: buildTrendDatasets(payload)
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        boxWidth: 8,
                        padding: 18
                    }
                },
                tooltip: {
                    callbacks: {
                        label(context) {
                            const value = context.parsed.y;

                            if (value === null || value === undefined) {
                                return null;
                            }

                            return `${context.dataset.label}: ${value.toFixed(2)}%`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    suggestedMax: 100,
                    grid: {
                        drawBorder: false
                    },
                    ticks: {
                        callback(value) {
                            return `${value}%`;
                        }
                    }
                },
                x: {
                    grid: {
                        display: false,
                        drawBorder: false
                    },
                    ticks: {
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 10
                    }
                }
            }
        }
    });

    forecastCharts.set('forecast-trend-chart', chart);
}

function hydrateForecastUi() {
    renderResourceForecastCharts();
    renderTrendForecastChart();

    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function delayedForecastHydration() {
    window.setTimeout(hydrateForecastUi, 80);
}

document.addEventListener('DOMContentLoaded', hydrateForecastUi);

document.body.addEventListener('htmx:afterSwap', function(event) {
    if (
        event.detail.target &&
        (event.detail.target.id === 'forecast-section' || event.detail.target.id === 'forecast-page')
    ) {
        delayedForecastHydration();
    }
});

document.body.addEventListener('htmx:afterSettle', function() {
    delayedForecastHydration();
});

document.body.addEventListener('click', function(event) {
    const trigger = event.target.closest('[data-analytics-tab-button]');

    if (!trigger) {
        return;
    }

    delayedForecastHydration();
});
