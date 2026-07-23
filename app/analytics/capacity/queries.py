"""Compatibility exports backed by the versioned PromQL query catalog."""

from app.integrations.prometheus.query_profiles import get_query_expression

CURRENT_PODS_QUERY = get_query_expression('analytics.capacity.queries.CURRENT_PODS_QUERY')
CURRENT_WORKER_PODS_QUERY = get_query_expression('analytics.capacity.queries.CURRENT_WORKER_PODS_QUERY')
WORKER_CPU_USAGE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_CPU_USAGE_QUERY')
WORKER_MEMORY_USAGE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_MEMORY_USAGE_QUERY')
CPU_REQUESTS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.CPU_REQUESTS_TOTAL_QUERY')
CPU_LIMITS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.CPU_LIMITS_TOTAL_QUERY')
MEMORY_REQUESTS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.MEMORY_REQUESTS_TOTAL_QUERY')
MEMORY_LIMITS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.MEMORY_LIMITS_TOTAL_QUERY')
WORKER_CPU_REQUESTS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.WORKER_CPU_REQUESTS_TOTAL_QUERY')
WORKER_CPU_LIMITS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.WORKER_CPU_LIMITS_TOTAL_QUERY')
WORKER_MEMORY_REQUESTS_TOTAL_QUERY = get_query_expression(
    'analytics.capacity.queries.WORKER_MEMORY_REQUESTS_TOTAL_QUERY'
)
WORKER_MEMORY_LIMITS_TOTAL_QUERY = get_query_expression('analytics.capacity.queries.WORKER_MEMORY_LIMITS_TOTAL_QUERY')
CPU_PEAK_QUERY_TEMPLATE = get_query_expression('analytics.capacity.queries.CPU_PEAK_QUERY_TEMPLATE')
MEMORY_PEAK_QUERY_TEMPLATE = get_query_expression('analytics.capacity.queries.MEMORY_PEAK_QUERY_TEMPLATE')
WORKER_CPU_PEAK_QUERY_TEMPLATE = get_query_expression('analytics.capacity.queries.WORKER_CPU_PEAK_QUERY_TEMPLATE')
WORKER_MEMORY_PEAK_QUERY_TEMPLATE = get_query_expression('analytics.capacity.queries.WORKER_MEMORY_PEAK_QUERY_TEMPLATE')
WORKER_CPU_ALLOCATABLE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_CPU_ALLOCATABLE_QUERY')
WORKER_MEMORY_ALLOCATABLE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_MEMORY_ALLOCATABLE_QUERY')
WORKER_POD_ALLOCATABLE_QUERY = get_query_expression('analytics.capacity.queries.WORKER_POD_ALLOCATABLE_QUERY')
