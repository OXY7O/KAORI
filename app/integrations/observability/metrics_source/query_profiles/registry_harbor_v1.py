from __future__ import annotations

from app.integrations.observability.metrics_source.query_profiles.registry import (
    QueryReference,
    query_reference,
    register_query_profile,
)
from app.integrations.observability.metrics_source.query_profiles.types import QueryDefinition

PROFILE_KEY = 'registry-harbor-v1'
PROFILE_VERSION = 1
PROFILE_LABEL = 'Harbor Registry Metrics v1'

QUERIES: dict[str, QueryDefinition] = {
    'registry.health': QueryDefinition(
        key='registry.health',
        expression='max(harbor_health)',
        domain='registry_health',
        required_metrics=('harbor_health',),
    ),
    'registry.component.up': QueryDefinition(
        key='registry.component.up',
        expression='min(harbor_up)',
        domain='registry_health',
        required_metrics=('harbor_up',),
    ),
    'registry.system.info': QueryDefinition(
        key='registry.system.info',
        expression='max(harbor_system_info)',
        domain='registry_identity',
        required_metrics=('harbor_system_info',),
    ),
    'registry.projects.total': QueryDefinition(
        key='registry.projects.total',
        expression='sum(harbor_project_total)',
        domain='registry_inventory_metrics',
        required_metrics=('harbor_project_total',),
        readiness_tier='recommended',
    ),
    'registry.project.artifacts': QueryDefinition(
        key='registry.project.artifacts',
        expression='sum by (project_name) (harbor_project_artifact_total)',
        domain='registry_inventory_metrics',
        required_metrics=('harbor_project_artifact_total',),
        required_labels=(('harbor_project_artifact_total', ('project_name',)),),
        readiness_tier='recommended',
    ),
    'registry.project.quota.usage_bytes': QueryDefinition(
        key='registry.project.quota.usage_bytes',
        expression='max by (project_name) (harbor_project_quota_usage_byte)',
        domain='registry_capacity',
        required_metrics=('harbor_project_quota_usage_byte',),
        required_labels=(('harbor_project_quota_usage_byte', ('project_name',)),),
        readiness_tier='recommended',
    ),
    'registry.project.quota.bytes': QueryDefinition(
        key='registry.project.quota.bytes',
        expression='max by (project_name) (harbor_project_quota_byte)',
        domain='registry_capacity',
        required_metrics=('harbor_project_quota_byte',),
        required_labels=(('harbor_project_quota_byte', ('project_name',)),),
        readiness_tier='recommended',
    ),
    'registry.project.pull_count': QueryDefinition(
        key='registry.project.pull_count',
        expression='max by (project_name) (harbor_artifact_pulled)',
        domain='registry_activity',
        required_metrics=('harbor_artifact_pulled',),
        required_labels=(('harbor_artifact_pulled', ('project_name',)),),
        readiness_tier='optional',
    ),
    'registry.core.request_rate': QueryDefinition(
        key='registry.core.request_rate',
        expression='sum(rate(harbor_core_http_request_total[5m]))',
        domain='registry_performance',
        required_metrics=('harbor_core_http_request_total',),
        required_history='5m',
        readiness_tier='recommended',
    ),
    'registry.core.inflight': QueryDefinition(
        key='registry.core.inflight',
        expression='sum(harbor_core_http_inflight_requests)',
        domain='registry_performance',
        required_metrics=('harbor_core_http_inflight_requests',),
        readiness_tier='optional',
    ),
    'registry.backend.request_rate': QueryDefinition(
        key='registry.backend.request_rate',
        expression='sum(rate(registry_http_requests_total[5m]))',
        domain='registry_performance',
        required_metrics=('registry_http_requests_total',),
        required_history='5m',
        readiness_tier='optional',
    ),
    'registry.task.queue_size': QueryDefinition(
        key='registry.task.queue_size',
        expression='sum(harbor_task_queue_size)',
        domain='registry_jobs',
        required_metrics=('harbor_task_queue_size',),
        readiness_tier='optional',
    ),
}


def get_registry_query(key: str) -> QueryDefinition:
    try:
        return QUERIES[key]
    except KeyError as exc:
        raise LookupError(f'Registry metrics query key is not registered: {key}') from exc


register_query_profile(adapter_key='prometheus_http', profile_key=PROFILE_KEY, queries=QUERIES)


def get_registry_query_expression(key: str) -> QueryReference:
    return query_reference(profile_key=PROFILE_KEY, query=get_registry_query(key))


def list_registry_queries(*, domain: str | None = None) -> tuple[QueryDefinition, ...]:
    values = QUERIES.values()
    if domain:
        values = (item for item in values if item.domain == domain)
    return tuple(values)
