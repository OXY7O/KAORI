from __future__ import annotations

from typing import Any

from flask import url_for

from app.common.pagination import paginate_sequence
from app.extensions.db import db
from app.integrations.binding_selectors import selector_form_values, selector_is_configured, selector_summary
from app.integrations.consumer_assets import build_consumer_asset_groups
from app.integrations.deletion import provider_deletion_guard
from app.integrations.observability.metrics_source.application.resolver import (
    MetricsSourceResolution,
    resolve_metrics_sources,
)
from app.integrations.observability.metrics_source.binding_profiles import get_binding_validation_profile
from app.integrations.observability.metrics_source.capabilities import PROVIDER_CAPABILITY_KEYS
from app.integrations.observability.metrics_source.capabilities import definition as capability_definition
from app.integrations.observability.metrics_source.providers import provider_definition
from app.integrations.observability.metrics_source.routing import normalize_routing_policy, recent_window_hours
from app.integrations.observability.metrics_source.scope import KUBERNETES_CLUSTER_SCOPE, bindings_for_instance
from app.integrations.readiness import resolve_binding_operational_status
from app.integrations.registry import get_integration
from app.integrations.runtime.presentation import runtime_history_view, runtime_state_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.models import Cluster, MetricsSource, ObjectStorageSystem
from app.models.integration import IntegrationBinding

_CORE_CAPABILITIES = set(PROVIDER_CAPABILITY_KEYS)

_RESOLUTION_CONSUMERS: tuple[dict[str, Any], ...] = (
    {
        'key': 'overview',
        'label': 'Kubernetes Overview',
        'icon': 'layout-dashboard',
        'binding_capabilities': ('metrics',),
        'technical_capabilities': ('instant_query', 'kubernetes_identity'),
    },
    {
        'key': 'utilization',
        'label': 'Utilization Analytics',
        'icon': 'gauge',
        'binding_capabilities': ('metrics', 'utilization'),
        'technical_capabilities': (
            'instant_query',
            'range_query',
            'kubernetes_identity',
            'utilization_metrics',
            'node_filesystem_identity',
        ),
    },
    {
        'key': 'capacity',
        'label': 'Capacity Analytics',
        'icon': 'cpu',
        'binding_capabilities': ('metrics', 'capacity'),
        'technical_capabilities': (
            'instant_query',
            'range_query',
            'kubernetes_identity',
            'capacity_metrics',
            'resource_requests_limits',
        ),
    },
    {
        'key': 'storage',
        'label': 'Storage Analytics',
        'icon': 'database',
        'binding_capabilities': ('metrics', 'storage'),
        'technical_capabilities': (
            'instant_query',
            'kubernetes_identity',
            'pvc_usage',
            'node_filesystem_identity',
        ),
    },
    {
        'key': 'workload',
        'label': 'Workload Analytics',
        'icon': 'boxes',
        'binding_capabilities': ('metrics', 'workload'),
        'technical_capabilities': (
            'instant_query',
            'range_query',
            'kubernetes_identity',
            'workload_metrics',
            'resource_requests_limits',
        ),
    },
    {
        'key': 'forecast',
        'label': 'Forecast',
        'icon': 'chart-spline',
        'binding_capabilities': ('metrics', 'forecast'),
        'technical_capabilities': ('range_query', 'long_term_history', 'capacity_metrics'),
    },
    {
        'key': 'top_consumers',
        'label': 'Top Consumers',
        'icon': 'list-ordered',
        'binding_capabilities': ('metrics', 'top_consumers'),
        'technical_capabilities': (
            'instant_query',
            'kubernetes_identity',
            'workload_metrics',
            'resource_requests_limits',
            'capacity_metrics',
            'pvc_usage',
        ),
    },
)


def build_instance_context(
    instance: MetricsSource,
    *,
    page: int = 1,
    per_page: int = 5,
    history_trigger: str = '',
    history_health: str = '',
    history_readiness: str = '',
    binding_page: int = 1,
    binding_per_page: int = 5,
) -> dict[str, Any]:
    bindings = bindings_for_instance(instance)
    consumer_asset_groups = build_consumer_asset_groups(
        lambda asset_type: get_binding_validation_profile(instance.adapter_key, asset_type)
    )
    available_capabilities: set[str] = {
        str(item) for item in ((instance.capabilities or {}).get('available') or ()) if item
    }
    assessments: list[dict[str, Any]] = [
        item for item in ((instance.capabilities or {}).get('assessments') or ()) if isinstance(item, dict)
    ]
    assessment_map = {str(item.get('key') or ''): item for item in assessments if item.get('key')}
    runtime_state = runtime_state_view(
        get_integration('metrics_source').runtime_state(instance),
        actions={
            'refresh_url': url_for('metrics.refresh_runtime', instance_id=instance.id),
            'configuration_url': url_for('metrics.instance_detail', instance_id=instance.id, _anchor='configuration'),
            'history_url': url_for('metrics.instance_runtime_history', instance_id=instance.id),
        },
    )
    rows, pagination = paginate_runtime_history(
        'metrics_source',
        str(instance.id),
        page=page,
        per_page=per_page,
        trigger_type=history_trigger,
        health_status=history_health,
        readiness=history_readiness,
    )
    capability_rows: list[dict[str, Any]] = [
        _capability_row(assessment_map.get(key, {'key': key, 'status': 'not_observed'}))
        for key in PROVIDER_CAPABILITY_KEYS
    ]
    observed_keys: set[str] = {str(row['key']) for row in capability_rows if row['available']}

    deletion_guard = provider_deletion_guard(
        integration_type='metrics_source',
        integration_instance_id=instance.integration_instance_id,
    )
    binding_rows = [_binding_row(binding, instance) for binding in bindings]
    binding_registry_rows, binding_registry_pagination = paginate_sequence(
        binding_rows,
        page=binding_page,
        per_page=binding_per_page,
    )

    return {
        'instance': instance,
        'provider': provider_definition(instance.provider_key),
        'bindings': bindings,
        'deletion_guard': deletion_guard,
        'binding_rows': binding_rows,
        'binding_registry_rows': binding_registry_rows,
        'binding_registry_pagination': binding_registry_pagination,
        'consumer_asset_groups': consumer_asset_groups,
        'metrics_recent_window_hours': recent_window_hours(),
        'capability_rows': capability_rows,
        'capability_summary': {
            'total': len(capability_rows),
            'observed': len(observed_keys),
            'required_missing': sum(1 for row in capability_rows if row['required'] and not row['available']),
            'optional_missing': sum(1 for row in capability_rows if not row['required'] and not row['available']),
        },
        'module_readiness_rows': _module_readiness_rows(instance, available_capabilities),
        'source_resolution_rows': _source_resolution_rows(instance, bindings),
        'runtime_state': runtime_state,
        'runtime_history': runtime_history_view(rows, pagination=pagination),
        'stats': {
            'bindings': len(bindings),
            'capabilities': len(available_capabilities),
            'ready': instance.readiness_status == 'ready',
        },
    }


def build_runtime_history_context(
    instance: MetricsSource,
    *,
    page: int = 1,
    per_page: int = 5,
    history_trigger: str = '',
    history_health: str = '',
    history_readiness: str = '',
) -> dict[str, object]:
    rows, pagination = paginate_runtime_history(
        'metrics_source',
        str(instance.id),
        page=page,
        per_page=per_page,
        trigger_type=history_trigger,
        health_status=history_health,
        readiness=history_readiness,
    )
    return runtime_history_view(rows, pagination=pagination)


def _capability_row(item: dict[str, Any]) -> dict[str, Any]:
    key = str(item.get('key') or '')
    definition = capability_definition(key)
    status = str(item.get('status') or 'not_observed')
    available = status == 'available'
    required = key in _CORE_CAPABILITIES
    status_tone = 'normal' if available else ('critical' if required else 'warning')
    status_icon = 'circle-check' if available else ('octagon-alert' if required else 'triangle-alert')
    technical_checks: list[dict[str, Any]] = [
        check for check in (item.get('technical_checks') or ()) if isinstance(check, dict)
    ]
    validation_query = item.get('validation_query')
    expected_signals = list(item.get('expected_signals') or (definition.expected_signals if definition else ()))
    required_by = list(item.get('required_by') or (definition.required_by if definition else ()))
    source_owner = str(
        item.get('source_owner') or (definition.source_owner if definition else 'configured metrics pipeline')
    )
    recommendation = str(
        item.get('recommendation')
        or (definition.recommendation if definition else 'Review the metrics pipeline and rerun Full Validation.')
    )
    possible_causes = [str(value) for value in item.get('possible_causes') or () if value]

    if validation_query and not any(check.get('query') for check in technical_checks):
        technical_checks.insert(
            0,
            {
                'label': 'Validation Query',
                'status': 'available' if available else status,
                'status_label': 'Ready' if available else status.replace('_', ' ').title(),
                'evidence': item.get('observed')
                or item.get('evidence')
                or 'The validator did not record a query result.',
                'query': str(validation_query),
                'registered_query': str(validation_query),
            },
        )

    return {
        'key': key,
        'label': item.get('label') or (definition.label if definition else key.replace('_', ' ').title()),
        'category': _capability_category(key),
        'description': _capability_description(required_by, source_owner),
        'required': required,
        'available': available,
        'status_label': item.get('status_label') or status.replace('_', ' ').title(),
        'status_tone': status_tone,
        'status_icon': status_icon,
        'evidence': item.get('observed') or item.get('evidence') or 'No technical evidence recorded.',
        'probe': _probe_reason(key, required_by, source_owner),
        'success_criteria': item.get('expected') or _expected_criteria(expected_signals),
        'configuration_guidance': recommendation,
        'impact': item.get('impact') or (definition.impact if definition else 'Dependent analytics may be degraded.'),
        'next_action': (
            'No immediate change is required. Revalidate after endpoint, recording-rule, exporter, or label-schema changes.'
            if available
            else recommendation
        ),
        'remediation': _remediation_steps(recommendation, possible_causes),
        'technical_checks': [_technical_check_row(check) for check in technical_checks],
        'expected_signals': expected_signals,
        'required_by': required_by,
        'source_owner': source_owner,
    }


def _technical_check_row(check: dict[str, Any]) -> dict[str, Any]:
    status = str(check.get('status') or 'not_observed')
    return {
        'label': str(check.get('label') or 'Technical Check'),
        'status': status,
        'status_label': str(check.get('status_label') or status.replace('_', ' ').title()),
        'evidence': str(check.get('evidence') or 'No evidence recorded.'),
        'query': str(check.get('query') or ''),
        'registered_query': str(check.get('registered_query') or ''),
        'series_count_display': str(check.get('series_count_display') or ''),
        'value_summary': str(check.get('value_summary') or ''),
        'error_detail': str(check.get('error_detail') or ''),
        'tone': 'normal'
        if status in {'available', 'ready'}
        else ('critical' if status in {'missing', 'misconfigured', 'unsupported', 'failed'} else 'warning'),
        'icon': 'circle-check'
        if status in {'available', 'ready'}
        else ('octagon-alert' if status in {'missing', 'misconfigured', 'unsupported', 'failed'} else 'triangle-alert'),
    }


def _probe_reason(key: str, required_by: list[str], source_owner: str) -> str:
    consumers = ', '.join(required_by) if required_by else 'KAORI operational consumers'
    return (
        f'KAORI checks this capability to confirm that {source_owner} can provide reliable evidence '
        f'for {consumers}. Exact executable queries are available under Technical Checks.'
    )


def _capability_category(key: str) -> str:
    if key in {'instant_query', 'range_query'}:
        return 'Query API'
    if key == 'long_term_history':
        return 'Retention'
    if key in {'pvc_usage', 'node_filesystem_identity'}:
        return 'Storage'
    if key in {'workload_metrics', 'resource_requests_limits'}:
        return 'Workload'
    if key in {'capacity_metrics', 'utilization_metrics'}:
        return 'Analytics Metrics'
    return 'Kubernetes Metrics'


def _capability_description(required_by: list[str], source_owner: str) -> str:
    consumers = ', '.join(required_by) if required_by else 'KAORI metrics consumers'
    return f'Required by {consumers}. Evidence is supplied by {source_owner}.'


def _expected_criteria(expected_signals: list[str]) -> str:
    if expected_signals:
        return f'The required query contract returns usable data with these signals: {", ".join(expected_signals)}.'
    return 'The exact registered query or API contract returns a successful, usable response.'


def _remediation_steps(recommendation: str, possible_causes: list[str]) -> list[str]:
    steps = [recommendation]
    for cause in possible_causes[:3]:
        steps.append(f'Check whether this condition applies: {cause}')
    steps.append('Run Full Validation again and confirm the capability and dependent module return to Ready.')
    return steps[:5]


def _module_readiness_rows(
    instance: MetricsSource,
    available_capabilities: set[str],
) -> list[dict[str, Any]]:
    required = tuple(PROVIDER_CAPABILITY_KEYS)
    missing = [key for key in required if key not in available_capabilities]
    if not instance.last_validated_at:
        status = 'not_observed'
    elif missing:
        status = 'degraded'
    else:
        status = 'ready'
    return [
        {
            'key': 'metrics_source_core',
            'label': 'Metrics Source Core Runtime',
            'description': 'Provider-neutral adapter and query capabilities required before any consumer binding is eligible.',
            'status': status,
            'required_capability_labels': [_capability_label(key) for key in required],
            'optional_capability_labels': [],
            'missing_required_labels': [_capability_label(key) for key in missing],
            'missing_optional_labels': [],
            'operator_guidance': (
                'Run Full Validation to establish the provider-level core contract.'
                if status == 'not_observed'
                else (
                    'No provider-level action is required. Validate each Kubernetes, MinIO, or future consumer through its binding.'
                    if status == 'ready'
                    else 'Restore the missing provider-level API capability, then rerun Full Validation.'
                )
            ),
            'ready_count': len(required) - len(missing),
            'query_count': len(required),
            'blocked_count': len(missing),
        }
    ]


def _capability_label(key: str) -> str:
    item = capability_definition(key)
    return item.label if item else key.replace('_', ' ').title()


def _binding_row(binding: IntegrationBinding, source: MetricsSource) -> dict[str, Any]:
    cluster = db.session.get(Cluster, binding.asset_key) if binding.asset_type == KUBERNETES_CLUSTER_SCOPE else None
    object_storage = (
        db.session.get(ObjectStorageSystem, binding.asset_key)
        if binding.asset_type == 'object_storage_system'
        else None
    )
    profile = get_binding_validation_profile(source.adapter_key, binding.asset_type)
    selector_values = selector_form_values(binding.selector_json)
    source_readiness = source.readiness_status or 'validation_required'
    operational = resolve_binding_operational_status(
        source_readiness=source_readiness,
        binding_validation=binding.validation_status,
        source_enabled=source.enabled,
        binding_enabled=binding.enabled,
    )
    scope_label = (
        cluster.name
        if cluster is not None
        else (object_storage.name if object_storage is not None else binding.asset_key)
    )
    scope_type_label = (
        'Kubernetes Cluster'
        if binding.asset_type == KUBERNETES_CLUSTER_SCOPE
        else (
            'Object Storage System'
            if binding.asset_type == 'object_storage_system'
            else binding.asset_type.replace('_', ' ').title()
        )
    )
    routing_policy = normalize_routing_policy(binding.routing_policy)
    return {
        'binding': binding,
        'scope_label': scope_label,
        'scope_type_label': scope_type_label,
        'consumer_profile': binding.validation_profile or (profile.profile_key if profile else 'Not Registered'),
        'consumer_profile_label': profile.label if profile else binding.validation_profile or 'Not Registered',
        'selector_summary': selector_summary(binding.selector_json),
        'selector_configured': selector_is_configured(binding.selector_json),
        'selector_label': selector_values['label'],
        'selector_operator': selector_values['operator'],
        'selector_value': selector_values['value'],
        'validation_status': binding.validation_status or 'validation_required',
        'source_readiness': source_readiness,
        'operational_status': operational['status'],
        'operational_label': operational['label'],
        'query_horizon': routing_policy['query_horizon'],
        'routing_weight': routing_policy['weight'],
    }


def _source_resolution_rows(
    current_instance: MetricsSource,
    bindings: list[IntegrationBinding],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for binding in bindings:
        if binding.asset_type != KUBERNETES_CLUSTER_SCOPE or binding.asset_key in seen:
            continue
        seen.add(binding.asset_key)
        cluster = db.session.get(Cluster, binding.asset_key)
        consumers = {
            definition['key']: _resolution_view(
                resolve_metrics_sources(
                    scope_type=KUBERNETES_CLUSTER_SCOPE,
                    scope_key=binding.asset_key,
                    required_binding_capabilities=definition['binding_capabilities'],
                    required_technical_capabilities=definition['technical_capabilities'],
                ),
                current_instance_id=current_instance.id,
                label=definition['label'],
                icon=definition['icon'],
            )
            for definition in _RESOLUTION_CONSUMERS
        }
        rows.append(
            {
                'scope_type': binding.asset_type,
                'scope_type_label': 'Managed Cluster',
                'scope_key': binding.asset_key,
                'scope_label': cluster.name if cluster is not None else binding.asset_key,
                'consumers': consumers,
            }
        )
    return rows


def _resolution_view(
    resolution: MetricsSourceResolution,
    *,
    current_instance_id: int,
    label: str,
    icon: str,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    selected = resolution.selected
    for candidate in resolution.candidates:
        row = {
            'instance_id': candidate.instance.id,
            'instance_name': candidate.instance.name,
            'binding_id': candidate.binding.id,
            'binding_role': candidate.binding.binding_role,
            'priority': candidate.binding.priority,
            'query_horizon': candidate.query_horizon,
            'routing_weight': candidate.routing_weight,
            'provider_key': candidate.provider_key,
            'eligible': candidate.eligible,
            'decision_reason': candidate.decision_reason,
            'missing_capability_labels': [_capability_label(key) for key in candidate.missing_technical_capabilities],
            'missing_binding_capabilities': list(candidate.missing_binding_capabilities),
            'operational_state': candidate.operational_state,
            'is_current_instance': candidate.instance.id == current_instance_id,
            'is_selected': bool(
                selected
                and selected.instance.id == candidate.instance.id
                and selected.binding.id == candidate.binding.id
            ),
        }
        candidates.append(row)
    return {
        'label': label,
        'icon': icon,
        'required_capabilities': [_capability_label(key) for key in resolution.required_technical_capabilities],
        'selected_instance_id': selected.instance.id if selected else None,
        'selected_instance_name': selected.instance.name if selected else None,
        'selected_role': selected.binding.binding_role if selected else None,
        'selected_operational_state': selected.operational_state if selected else 'unavailable',
        'current_instance_selected': bool(selected and selected.instance.id == current_instance_id),
        'candidates': candidates,
    }
