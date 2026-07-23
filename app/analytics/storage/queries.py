"""Compatibility exports backed by the versioned PromQL query catalog."""

from app.integrations.prometheus.query_profiles import get_query_expression

NAMESPACE_ACTIVE_QUERY = get_query_expression('analytics.storage.queries.NAMESPACE_ACTIVE_QUERY')
NODE_VAR_FILESYSTEM_SIZE_QUERY = get_query_expression('analytics.storage.queries.NODE_VAR_FILESYSTEM_SIZE_QUERY')
NODE_VAR_FILESYSTEM_AVAILABLE_QUERY = get_query_expression(
    'analytics.storage.queries.NODE_VAR_FILESYSTEM_AVAILABLE_QUERY'
)
NODE_ROOT_FILESYSTEM_SIZE_QUERY = get_query_expression('analytics.storage.queries.NODE_ROOT_FILESYSTEM_SIZE_QUERY')
NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY = get_query_expression(
    'analytics.storage.queries.NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY'
)
PVC_REQUESTED_TOTAL_QUERY = get_query_expression('analytics.storage.queries.PVC_REQUESTED_TOTAL_QUERY')
PVC_USED_TOTAL_QUERY = get_query_expression('analytics.storage.queries.PVC_USED_TOTAL_QUERY')
PVC_AVAILABLE_TOTAL_QUERY = get_query_expression('analytics.storage.queries.PVC_AVAILABLE_TOTAL_QUERY')
PVC_REQUESTED_BY_CLAIM_QUERY = get_query_expression('analytics.storage.queries.PVC_REQUESTED_BY_CLAIM_QUERY')
PVC_USED_BY_CLAIM_QUERY = get_query_expression('analytics.storage.queries.PVC_USED_BY_CLAIM_QUERY')
PVC_AVAILABLE_BY_CLAIM_QUERY = get_query_expression('analytics.storage.queries.PVC_AVAILABLE_BY_CLAIM_QUERY')
PVC_STATUS_BY_CLAIM_QUERY = get_query_expression('analytics.storage.queries.PVC_STATUS_BY_CLAIM_QUERY')
PVC_INFO_QUERY = get_query_expression('analytics.storage.queries.PVC_INFO_QUERY')
PVC_COUNT_QUERY = get_query_expression('analytics.storage.queries.PVC_COUNT_QUERY')
PV_CAPACITY_QUERY = get_query_expression('analytics.storage.queries.PV_CAPACITY_QUERY')
PV_CAPACITY_BY_VOLUME_QUERY = get_query_expression('analytics.storage.queries.PV_CAPACITY_BY_VOLUME_QUERY')
PV_COUNT_QUERY = get_query_expression('analytics.storage.queries.PV_COUNT_QUERY')
PV_INFO_QUERY = get_query_expression('analytics.storage.queries.PV_INFO_QUERY')
PV_STATUS_BY_VOLUME_QUERY = get_query_expression('analytics.storage.queries.PV_STATUS_BY_VOLUME_QUERY')
PV_RECLAIM_POLICY_QUERY = get_query_expression('analytics.storage.queries.PV_RECLAIM_POLICY_QUERY')
