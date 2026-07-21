"""Compatibility exports backed by the versioned PromQL query catalog."""

from app.integrations.prometheus.query_profiles import get_query_expression

CLUSTER_NODE_COUNT = get_query_expression('prometheus.queries.CLUSTER_NODE_COUNT')
CLUSTER_NAMESPACE_COUNT = get_query_expression('prometheus.queries.CLUSTER_NAMESPACE_COUNT')
CLUSTER_POD_COUNT = get_query_expression('prometheus.queries.CLUSTER_POD_COUNT')
CLUSTER_CPU_CAPACITY = get_query_expression('prometheus.queries.CLUSTER_CPU_CAPACITY')
CLUSTER_CPU_USAGE = get_query_expression('prometheus.queries.CLUSTER_CPU_USAGE')
CLUSTER_CPU_UTILIZATION = get_query_expression('prometheus.queries.CLUSTER_CPU_UTILIZATION')
CLUSTER_MEMORY_CAPACITY = get_query_expression('prometheus.queries.CLUSTER_MEMORY_CAPACITY')
CLUSTER_MEMORY_USAGE = get_query_expression('prometheus.queries.CLUSTER_MEMORY_USAGE')
CLUSTER_MEMORY_UTILIZATION = get_query_expression('prometheus.queries.CLUSTER_MEMORY_UTILIZATION')
CLUSTER_STORAGE_CAPACITY = get_query_expression('prometheus.queries.CLUSTER_STORAGE_CAPACITY')
CLUSTER_STORAGE_USAGE = get_query_expression('prometheus.queries.CLUSTER_STORAGE_USAGE')
CLUSTER_STORAGE_AVAILABLE = get_query_expression('prometheus.queries.CLUSTER_STORAGE_AVAILABLE')
CLUSTER_STORAGE_UTILIZATION = get_query_expression('prometheus.queries.CLUSTER_STORAGE_UTILIZATION')
TOP_CPU_PODS = get_query_expression('prometheus.queries.TOP_CPU_PODS')
TOP_MEMORY_PODS = get_query_expression('prometheus.queries.TOP_MEMORY_PODS')
CPU_USAGE_HISTORY = get_query_expression('prometheus.queries.CPU_USAGE_HISTORY')
MEMORY_USAGE_HISTORY = get_query_expression('prometheus.queries.MEMORY_USAGE_HISTORY')
STORAGE_USAGE_HISTORY = get_query_expression('prometheus.queries.STORAGE_USAGE_HISTORY')
