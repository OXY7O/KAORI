let forecastChart = null;

        function getForecastChartData() {
            const element = document.getElementById('forecast-chart-data');

            if (!element) {
                return null;
            }

            try {
                return JSON.parse(element.textContent);
            } catch {
                return null;
            }
        }

        function buildForecastDatasets(payload) {
            const datasets = [];

            payload.datasets.forEach((item) => {
                datasets.push({
                    label: `${item.label} Historical`,
                    data: item.historical,
                    borderWidth: 2,
                    tension: 0.35,
                    pointRadius: 0
                });

                datasets.push({
                    label: `${item.label} Forecast`,
                    data: item.forecast,
                    borderWidth: 2,
                    borderDash: [6, 6],
                    tension: 0.35,
                    pointRadius: 0
                });
            });

            if (payload.datasets.length > 0) {
                const labelsLength = payload.datasets[0].labels.length;

                datasets.push({
                    label: 'Warning 75%',
                    data: Array(labelsLength).fill(payload.warning_threshold),
                    borderWidth: 1,
                    borderDash: [4, 4],
                    pointRadius: 0
                });

                datasets.push({
                    label: 'Critical 90%',
                    data: Array(labelsLength).fill(payload.critical_threshold),
                    borderWidth: 1,
                    borderDash: [2, 4],
                    pointRadius: 0
                });
            }

            return datasets;
        }

        function renderForecastChart() {
            const canvas = document.getElementById('forecast-chart');

            if (!canvas || typeof Chart === 'undefined') {
                return;
            }

            const payload = getForecastChartData();

            if (!payload || !payload.datasets || payload.datasets.length === 0) {
                return;
            }

            const labels = payload.datasets[0].labels;

            if (forecastChart !== null) {
                forecastChart.destroy();
            }

            forecastChart = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: buildForecastDatasets(payload)
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
                                boxWidth: 8
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
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
                            ticks: {
                                callback: function(value) {
                                    return `${value}%`;
                                }
                            }
                        },
                        x: {
                            ticks: {
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 8
                            }
                        }
                    }
                }
            });
        }

        function hydrateForecastUi() {
            renderForecastChart();

            if (window.lucide) {
                window.lucide.createIcons();
            }
        }

        document.addEventListener(
            'DOMContentLoaded',
            hydrateForecastUi
        );

        document.body.addEventListener(
            'htmx:afterSwap',
            function(event) {
                if (
                    event.detail.target &&
                    (
                        event.detail.target.id === 'forecast-section' ||
                        event.detail.target.id === 'forecast-page'
                    )
                ) {
                    hydrateForecastUi();
                }
            }
        );

        document.body.addEventListener(
            'htmx:afterSettle',
            hydrateForecastUi
        );
