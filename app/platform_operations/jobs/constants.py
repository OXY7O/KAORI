from __future__ import annotations

ACTIVE_JOB_STATUSES = ('queued', 'running', 'retrying', 'cancel_requested')
TERMINAL_JOB_STATUSES = ('succeeded', 'partially_succeeded', 'failed', 'canceled', 'expired')

WORKLOAD_STANDARD = 'standard'
WORKLOAD_RUNTIME = 'runtime'
WORKLOAD_VALIDATION = 'validation'
WORKLOAD_ANALYTICS = 'analytics'
WORKLOAD_FORECASTING = 'forecasting'
HEAVY_WORKLOAD_CLASSES = (WORKLOAD_ANALYTICS, WORKLOAD_FORECASTING)

DEFAULT_PRIORITIES = {
    WORKLOAD_RUNTIME: 2,
    WORKLOAD_VALIDATION: 3,
    WORKLOAD_STANDARD: 5,
    WORKLOAD_ANALYTICS: 6,
    WORKLOAD_FORECASTING: 7,
}
