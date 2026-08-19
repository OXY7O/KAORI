from __future__ import annotations

from app.integrations.observability.metrics_source.query_profiles.registry import (
    QueryReference,
    query_reference,
    register_query_profile,
)
from app.integrations.observability.metrics_source.query_profiles.types import QueryDefinition

PROFILE_KEY = 'object-storage-minio-v2'
PROFILE_VERSION = 1
PROFILE_LABEL = 'MinIO Metrics v2'

QUERIES: dict[str, QueryDefinition] = {
    'object_storage.capacity.total_bytes': QueryDefinition(
        key='object_storage.capacity.total_bytes',
        expression='max(minio_cluster_capacity_usable_total_bytes)',
        domain='object_storage_capacity',
        required_metrics=('minio_cluster_capacity_usable_total_bytes',),
    ),
    'object_storage.capacity.free_bytes': QueryDefinition(
        key='object_storage.capacity.free_bytes',
        expression='max(minio_cluster_capacity_usable_free_bytes)',
        domain='object_storage_capacity',
        required_metrics=('minio_cluster_capacity_usable_free_bytes',),
    ),
    'object_storage.usage.total_bytes': QueryDefinition(
        key='object_storage.usage.total_bytes',
        expression='max(minio_cluster_usage_total_bytes)',
        domain='object_storage_capacity',
        required_metrics=('minio_cluster_usage_total_bytes',),
    ),
    'object_storage.usage.objects': QueryDefinition(
        key='object_storage.usage.objects',
        expression='max(minio_cluster_usage_object_total)',
        domain='object_storage_capacity',
        required_metrics=('minio_cluster_usage_object_total',),
    ),
    'object_storage.usage.buckets': QueryDefinition(
        key='object_storage.usage.buckets',
        expression='max(minio_cluster_bucket_total)',
        domain='object_storage_capacity',
        required_metrics=('minio_cluster_bucket_total',),
    ),
    'object_storage.health.offline_nodes': QueryDefinition(
        key='object_storage.health.offline_nodes',
        expression='max(minio_cluster_nodes_offline_total)',
        domain='object_storage_health',
        readiness_tier='recommended',
        required_metrics=('minio_cluster_nodes_offline_total',),
    ),
    'object_storage.requests.rate': QueryDefinition(
        key='object_storage.requests.rate',
        expression='sum(rate(minio_s3_requests_total[5m]))',
        domain='object_storage_performance',
        required_metrics=('minio_s3_requests_total',),
        required_history='5m',
    ),
    'object_storage.requests.error_rate': QueryDefinition(
        key='object_storage.requests.error_rate',
        expression='sum(rate(minio_s3_requests_errors_total[5m]))',
        domain='object_storage_performance',
        required_metrics=('minio_s3_requests_errors_total',),
        required_history='5m',
    ),
    'object_storage.requests.inflight': QueryDefinition(
        key='object_storage.requests.inflight',
        expression='sum(minio_s3_requests_inflight_total)',
        domain='object_storage_performance',
        readiness_tier='recommended',
        required_metrics=('minio_s3_requests_inflight_total',),
    ),
    'object_storage.requests.waiting': QueryDefinition(
        key='object_storage.requests.waiting',
        expression='sum(minio_s3_requests_waiting_total)',
        domain='object_storage_performance',
        readiness_tier='recommended',
        required_metrics=('minio_s3_requests_waiting_total',),
    ),
    'object_storage.traffic.received_bps': QueryDefinition(
        key='object_storage.traffic.received_bps',
        expression='sum(rate(minio_s3_traffic_received_bytes[5m]))',
        domain='object_storage_performance',
        readiness_tier='recommended',
        required_metrics=('minio_s3_traffic_received_bytes',),
        required_history='5m',
    ),
    'object_storage.traffic.sent_bps': QueryDefinition(
        key='object_storage.traffic.sent_bps',
        expression='sum(rate(minio_s3_traffic_sent_bytes[5m]))',
        domain='object_storage_performance',
        readiness_tier='recommended',
        required_metrics=('minio_s3_traffic_sent_bytes',),
        required_history='5m',
    ),
    'object_storage.bucket.usage': QueryDefinition(
        key='object_storage.bucket.usage',
        expression='max by (bucket) (minio_bucket_usage_total_bytes)',
        domain='object_storage_consumers',
        readiness_tier='recommended',
        required_metrics=('minio_bucket_usage_total_bytes',),
        required_labels=(('minio_bucket_usage_total_bytes', ('bucket',)),),
    ),
    'object_storage.bucket.usage_history': QueryDefinition(
        key='object_storage.bucket.usage_history',
        expression='max by (bucket) (minio_bucket_usage_total_bytes)',
        domain='object_storage_consumers',
        readiness_tier='recommended',
        required_metrics=('minio_bucket_usage_total_bytes',),
        required_labels=(('minio_bucket_usage_total_bytes', ('bucket',)),),
    ),
    'object_storage.bucket.objects': QueryDefinition(
        key='object_storage.bucket.objects',
        expression='max by (bucket) (minio_bucket_usage_object_total)',
        domain='object_storage_consumers',
        readiness_tier='recommended',
        required_metrics=('minio_bucket_usage_object_total',),
        required_labels=(('minio_bucket_usage_object_total', ('bucket',)),),
    ),
    'object_storage.bucket.quota': QueryDefinition(
        key='object_storage.bucket.quota',
        expression='max by (bucket) (minio_bucket_quota_total_bytes)',
        domain='object_storage_consumers',
        readiness_tier='optional',
        required_metrics=('minio_bucket_quota_total_bytes',),
        required_labels=(('minio_bucket_quota_total_bytes', ('bucket',)),),
    ),
    'object_storage.bucket.request_rate': QueryDefinition(
        key='object_storage.bucket.request_rate',
        expression='sum by (bucket) (rate(minio_bucket_requests_total[5m]))',
        domain='object_storage_consumers',
        readiness_tier='recommended',
        required_metrics=('minio_bucket_requests_total',),
        required_labels=(('minio_bucket_requests_total', ('bucket',)),),
        required_history='5m',
    ),
    'object_storage.bucket.error_rate': QueryDefinition(
        key='object_storage.bucket.error_rate',
        expression=('sum by (bucket) (rate({__name__=~"minio_bucket_requests_(4xx|5xx)_errors_total"}[5m]))'),
        domain='object_storage_consumers',
        readiness_tier='recommended',
        required_metrics=(
            'minio_bucket_requests_4xx_errors_total',
            'minio_bucket_requests_5xx_errors_total',
        ),
        required_labels=(
            ('minio_bucket_requests_4xx_errors_total', ('bucket',)),
            ('minio_bucket_requests_5xx_errors_total', ('bucket',)),
        ),
        required_history='5m',
    ),
}


def get_object_storage_query(key: str) -> QueryDefinition:
    try:
        return QUERIES[key]
    except KeyError as exc:
        raise LookupError(f'Object-storage metrics query key is not registered: {key}') from exc


register_query_profile(adapter_key='prometheus_http', profile_key=PROFILE_KEY, queries=QUERIES)


def get_object_storage_query_expression(key: str) -> QueryReference:
    return query_reference(profile_key=PROFILE_KEY, query=get_object_storage_query(key))


def list_object_storage_queries(*, domain: str | None = None) -> tuple[QueryDefinition, ...]:
    values = QUERIES.values()
    if domain:
        values = (item for item in values if item.domain == domain)
    return tuple(values)
