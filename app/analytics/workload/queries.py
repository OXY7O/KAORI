"""Compatibility exports backed by the versioned PromQL query catalog."""

from app.integrations.prometheus.query_profiles import get_query_expression

NAMESPACE_ACTIVE_QUERY = get_query_expression('analytics.workload.queries.NAMESPACE_ACTIVE_QUERY')
TENANT_QUOTA_HARD_QUERY = get_query_expression('analytics.workload.queries.TENANT_QUOTA_HARD_QUERY')
TENANT_QUOTA_USED_QUERY = get_query_expression('analytics.workload.queries.TENANT_QUOTA_USED_QUERY')
TENANT_CPU_ACTUAL_QUERY = get_query_expression('analytics.workload.queries.TENANT_CPU_ACTUAL_QUERY')
TENANT_MEMORY_ACTUAL_QUERY = get_query_expression('analytics.workload.queries.TENANT_MEMORY_ACTUAL_QUERY')
TENANT_POD_ACTUAL_QUERY = get_query_expression('analytics.workload.queries.TENANT_POD_ACTUAL_QUERY')
WORKLOAD_POD_OWNER_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_POD_OWNER_QUERY')
WORKLOAD_QOS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_QOS_QUERY')
WORKLOAD_CPU_REQUESTS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_REQUESTS_QUERY')
WORKLOAD_CPU_LIMITS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_LIMITS_QUERY')
WORKLOAD_CPU_AVG_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_AVG_QUERY')
WORKLOAD_CPU_PEAK_QUERY_TEMPLATE = get_query_expression('analytics.workload.queries.WORKLOAD_CPU_PEAK_QUERY_TEMPLATE')
WORKLOAD_MEMORY_REQUESTS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_MEMORY_REQUESTS_QUERY')
WORKLOAD_MEMORY_LIMITS_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_MEMORY_LIMITS_QUERY')
WORKLOAD_MEMORY_AVG_QUERY = get_query_expression('analytics.workload.queries.WORKLOAD_MEMORY_AVG_QUERY')
WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE = get_query_expression(
    'analytics.workload.queries.WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE'
)
