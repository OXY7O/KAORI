"""Compatibility exports backed by the versioned PromQL query catalog."""

from app.integrations.prometheus.query_profiles import get_query_expression

PROMETHEUS_ALERTS_QUERY = get_query_expression('analytics.alerts.queries.PROMETHEUS_ALERTS_QUERY')
PROMETHEUS_FIRING_ALERTS_QUERY = get_query_expression('analytics.alerts.queries.PROMETHEUS_FIRING_ALERTS_QUERY')
POD_RESTART_ANOMALY_QUERY = get_query_expression('analytics.alerts.queries.POD_RESTART_ANOMALY_QUERY')
POD_NOT_READY_ANOMALY_QUERY = get_query_expression('analytics.alerts.queries.POD_NOT_READY_ANOMALY_QUERY')
CPU_SPIKE_QUERY = get_query_expression('analytics.alerts.queries.CPU_SPIKE_QUERY')
MEMORY_USAGE_QUERY = get_query_expression('analytics.alerts.queries.MEMORY_USAGE_QUERY')
