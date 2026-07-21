"""Compatibility exports backed by the versioned PromQL query catalog."""

from app.integrations.prometheus.query_profiles import get_query_expression

NAMESPACE_ACTIVE_QUERY = get_query_expression('analytics.forecast.queries.NAMESPACE_ACTIVE_QUERY')
CPU_USAGE_QUERY = get_query_expression('analytics.forecast.queries.CPU_USAGE_QUERY')
CPU_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.forecast.queries.CPU_USAGE_BY_NAMESPACE_QUERY')
MEMORY_USAGE_QUERY = get_query_expression('analytics.forecast.queries.MEMORY_USAGE_QUERY')
MEMORY_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.forecast.queries.MEMORY_USAGE_BY_NAMESPACE_QUERY')
STORAGE_USAGE_QUERY = get_query_expression('analytics.forecast.queries.STORAGE_USAGE_QUERY')
STORAGE_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.forecast.queries.STORAGE_USAGE_BY_NAMESPACE_QUERY')
POD_USAGE_QUERY = get_query_expression('analytics.forecast.queries.POD_USAGE_QUERY')
POD_USAGE_BY_NAMESPACE_QUERY = get_query_expression('analytics.forecast.queries.POD_USAGE_BY_NAMESPACE_QUERY')
CPU_WORKER_CAPACITY_QUERY = get_query_expression('analytics.forecast.queries.CPU_WORKER_CAPACITY_QUERY')
MEMORY_WORKER_CAPACITY_QUERY = get_query_expression('analytics.forecast.queries.MEMORY_WORKER_CAPACITY_QUERY')
POD_WORKER_CAPACITY_QUERY = get_query_expression('analytics.forecast.queries.POD_WORKER_CAPACITY_QUERY')
STORAGE_CAPACITY_QUERY = get_query_expression('analytics.forecast.queries.STORAGE_CAPACITY_QUERY')
STORAGE_CAPACITY_BY_NAMESPACE_QUERY = get_query_expression('analytics.forecast.queries.STORAGE_CAPACITY_BY_NAMESPACE_QUERY')
