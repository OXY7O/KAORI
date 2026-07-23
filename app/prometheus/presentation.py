from __future__ import annotations

from typing import Any

from flask import url_for

from app.extensions.db import db
from app.integrations.binding_selectors import selector_form_values, selector_is_configured, selector_summary
from app.integrations.deletion import provider_deletion_guard
from app.integrations.prometheus.capabilities import CAPABILITIES
from app.integrations.prometheus.capabilities import definition as capability_definition
from app.integrations.prometheus.scope import KUBERNETES_CLUSTER_SCOPE, cluster_bindings_for_instance
from app.integrations.readiness import resolve_binding_operational_status
from app.integrations.registry import get_integration
from app.integrations.runtime.presentation import runtime_history_view, runtime_state_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.models import Cluster, PrometheusInstance
from app.models.integration import IntegrationBinding
from app.prometheus.resolver import PrometheusSourceResolution, resolve_prometheus_sources

_CORE_CAPABILITIES = {
    'instant_query',
    'range_query',
    'kubernetes_identity',
    'utilization_metrics',
    'capacity_metrics',
}

_MODULE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    'app.prometheus': ('instant_query', 'kubernetes_identity'),
    'app.analytics.utilization': ('instant_query', 'range_query', 'utilization_metrics'),
    'app.analytics.capacity': ('instant_query', 'range_query', 'capacity_metrics', 'resource_requests_limits'),
    'app.analytics.storage': ('instant_query', 'range_query', 'pvc_usage', 'node_filesystem_identity'),
    'app.analytics.workload': ('instant_query', 'range_query', 'workload_metrics'),
    'app.analytics.forecast': ('range_query', 'long_term_history'),
    'app.analytics.top_consumers': ('instant_query', 'resource_requests_limits', 'workload_metrics'),
}

_MODULE_DESCRIPTIONS: dict[str, str] = {
    'app.prometheus': 'Kubernetes overview and metric-source context.',
    'app.analytics.utilization': 'Current and historical CPU, memory, pod, and pressure utilization.',
    'app.analytics.capacity': 'Worker capacity, requests, limits, overcommit, and headroom.',
    'app.analytics.storage': 'PVC usage, node filesystem capacity, and storage trends.',
    'app.analytics.workload': 'Workload ownership, quota, QoS, placement, and right-sizing.',
    'app.analytics.forecast': 'Long-range trend windows and forecast inputs.',
    'app.analytics.top_consumers': 'Ranked workload and namespace consumption analysis.',
}

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
        'technical_capabilities': ('instant_query', 'range_query', 'utilization_metrics'),
    },
    {
        'key': 'capacity',
        'label': 'Capacity Analytics',
        'icon': 'cpu',
        'binding_capabilities': ('metrics', 'capacity'),
        'technical_capabilities': ('instant_query', 'range_query', 'capacity_metrics'),
    },
    {
        'key': 'storage',
        'label': 'Storage Analytics',
        'icon': 'database',
        'binding_capabilities': ('metrics', 'storage'),
        'technical_capabilities': ('instant_query', 'range_query', 'pvc_usage', 'node_filesystem_identity'),
    },
    {
        'key': 'workload',
        'label': 'Workload Analytics',
        'icon': 'boxes',
        'binding_capabilities': ('metrics', 'workload'),
        'technical_capabilities': ('instant_query', 'range_query', 'workload_metrics'),
    },
    {
        'key': 'forecast',
        'label': 'Forecast',
        'icon': 'chart-spline',
        'binding_capabilities': ('metrics', 'forecast'),
        'technical_capabilities': ('range_query', 'long_term_history'),
    },
)


def build_instance_context(
    instance: PrometheusInstance,
    *,
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    bindings = cluster_bindings_for_instance(instance)
    clusters = Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()
    available_capabilities = set((instance.capabilities or {}).get('available') or ())
    assessments = list((instance.capabilities or {}).get('assessments') or ())
    assessment_map = {str(item.get('key') or ''): item for item in assessments if item.get('key')}
    runtime_state = runtime_state_view(
        get_integration('prometheus').adapter.get_state(instance),
        actions={
            'refresh_url': url_for('prometheus.refresh_runtime', instance_id=instance.id),
            'configuration_url': url_for('prometheus.instance_detail', instance_id=instance.id, _anchor='configuration'),
            'history_url': url_for('prometheus.instance_runtime_history', instance_id=instance.id),
        },
    )
    rows, pagination = paginate_runtime_history(
        'prometheus',
        str(instance.id),
        page=page,
        per_page=per_page,
    )
    capability_rows = [
        _capability_row(assessment_map.get(key, {'key': key, 'status': 'not_observed'}))
        for key in CAPABILITIES
    ]
    observed_keys = {
        row['key']
        for row in capability_rows
        if row['available']
    }

    deletion_guard = provider_deletion_guard(
        provider_type='prometheus',
        provider_instance_id=instance.id,
    )

    return {
        'instance': instance,
        'bindings': bindings,
        'deletion_guard': deletion_guard,
        'binding_rows': [_binding_row(binding, instance) for binding in bindings],
        'clusters': clusters,
        'clusters_by_id': {cluster.id: cluster for cluster in clusters},
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
    instance: PrometheusInstance,
    *,
    page: int = 1,
    per_page: int = 5,
) -> dict[str, object]:
    rows, pagination = paginate_runtime_history(
        'prometheus',
        str(instance.id),
        page=page,
        per_page=per_page,
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
    technical_checks = list(item.get('technical_checks') or ())
    validation_query = item.get('validation_query') or (definition.validation_query if definition else None)
    expected_signals = list(item.get('expected_signals') or (definition.expected_signals if definition else ()))
    required_by = list(item.get('required_by') or (definition.required_by if definition else ()))
    source_owner = str(item.get('source_owner') or (definition.source_owner if definition else 'Prometheus-compatible metrics pipeline'))
    recommendation = str(item.get('recommendation') or (definition.recommendation if definition else 'Review the metrics pipeline and rerun Full Validation.'))
    possible_causes = [str(value) for value in item.get('possible_causes') or () if value]

    if validation_query and not any(check.get('query') for check in technical_checks):
        technical_checks.insert(0, {
            'label': 'Validation Query',
            'status': 'available' if available else status,
            'status_label': 'Ready' if available else status.replace('_', ' ').title(),
            'evidence': item.get('observed') or item.get('evidence') or 'The validator did not record a query result.',
            'query': str(validation_query),
            'registered_query': str(validation_query),
        })

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
        'tone': 'normal' if status in {'available', 'ready'} else ('critical' if status in {'missing', 'misconfigured', 'unsupported', 'failed'} else 'warning'),
        'icon': 'circle-check' if status in {'available', 'ready'} else ('octagon-alert' if status in {'missing', 'misconfigured', 'unsupported', 'failed'} else 'triangle-alert'),
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
        return f"The required query contract returns usable data with these signals: {', '.join(expected_signals)}."
    return 'The exact registered query or API contract returns a successful, usable response.'


def _remediation_steps(recommendation: str, possible_causes: list[str]) -> list[str]:
    steps = [recommendation]
    for cause in possible_causes[:3]:
        steps.append(f'Check whether this condition applies: {cause}')
    steps.append('Run Full Validation again and confirm the capability and dependent module return to Ready.')
    return steps[:5]


def _module_readiness_rows(
    instance: PrometheusInstance,
    available_capabilities: set[str],
) -> list[dict[str, Any]]:
    module_state = instance.module_readiness or {}
    rows: list[dict[str, Any]] = []
    for domain, required in _MODULE_REQUIREMENTS.items():
        state = module_state.get(domain) or {}
        missing = [key for key in required if key not in available_capabilities]
        if not instance.last_validated_at:
            default_status = 'not_observed'
        else:
            default_status = 'ready' if not missing else 'degraded'
        status = str(state.get('status') or default_status)
        if instance.last_validated_at and missing and status == 'ready':
            status = 'degraded'
        rows.append({
            'key': domain,
            'label': state.get('label') or domain.replace('app.analytics.', '').replace('app.', '').replace('_', ' ').title(),
            'description': _MODULE_DESCRIPTIONS.get(domain, 'Operational readiness derived from the latest query and capability evidence.'),
            'status': status,
            'required_capability_labels': [_capability_label(key) for key in required],
            'optional_capability_labels': [],
            'missing_required_labels': [_capability_label(key) for key in missing],
            'missing_optional_labels': [],
            'operator_guidance': (
                'Run Full Validation to establish the first module readiness contract.'
                if status == 'not_observed'
                else (
                    'No action is required. Revalidate after metrics, labels, query rules, retention, or endpoint behavior changes.'
                    if not missing and status == 'ready'
                    else f"Restore the missing capability evidence, then rerun Full Validation: {', '.join(_capability_label(key) for key in missing) or 'review blocked query contracts'}."
                )
            ),
            'ready_count': state.get('ready_count', 0),
            'query_count': state.get('query_count', 0),
            'blocked_count': state.get('blocked_count', 0),
        })
    return rows


def _capability_label(key: str) -> str:
    item = capability_definition(key)
    return item.label if item else key.replace('_', ' ').title()


def _binding_row(binding: IntegrationBinding, source: PrometheusInstance) -> dict[str, Any]:
    cluster = db.session.get(Cluster, binding.asset_key) if binding.asset_type == KUBERNETES_CLUSTER_SCOPE else None
    selector_values = selector_form_values(binding.selector_json)
    source_readiness = source.readiness_status or 'validation_required'
    operational = resolve_binding_operational_status(
        source_readiness=source_readiness,
        binding_validation=binding.validation_status,
        source_enabled=source.enabled,
        binding_enabled=binding.enabled,
    )
    return {
        'binding': binding,
        'scope_label': cluster.name if cluster is not None else binding.asset_key,
        'scope_type_label': 'Managed Cluster' if binding.asset_type == KUBERNETES_CLUSTER_SCOPE else binding.asset_type.replace('_', ' ').title(),
        'selector_summary': selector_summary(binding.selector_json),
        'selector_configured': selector_is_configured(binding.selector_json),
        'selector_label': selector_values['label'],
        'selector_operator': selector_values['operator'],
        'selector_value': selector_values['value'],
        'validation_status': binding.validation_status or 'validation_required',
        'source_readiness': source_readiness,
        'operational_status': operational['status'],
        'operational_label': operational['label'],
    }


def _source_resolution_rows(
    current_instance: PrometheusInstance,
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
                resolve_prometheus_sources(
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
        rows.append({
            'scope_type': binding.asset_type,
            'scope_type_label': 'Managed Cluster',
            'scope_key': binding.asset_key,
            'scope_label': cluster.name if cluster is not None else binding.asset_key,
            'consumers': consumers,
        })
    return rows


def _resolution_view(
    resolution: PrometheusSourceResolution,
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
            'eligible': candidate.eligible,
            'decision_reason': candidate.decision_reason,
            'missing_capability_labels': [
                _capability_label(key)
                for key in candidate.missing_technical_capabilities
            ],
            'missing_binding_capabilities': list(candidate.missing_binding_capabilities),
            'operational_state': candidate.operational_state,
            'is_current_instance': candidate.instance.id == current_instance_id,
            'is_selected': bool(selected and selected.instance.id == candidate.instance.id and selected.binding.id == candidate.binding.id),
        }
        candidates.append(row)
    return {
        'label': label,
        'icon': icon,
        'required_capabilities': [
            _capability_label(key)
            for key in resolution.required_technical_capabilities
        ],
        'selected_instance_id': selected.instance.id if selected else None,
        'selected_instance_name': selected.instance.name if selected else None,
        'selected_role': selected.binding.binding_role if selected else None,
        'selected_operational_state': selected.operational_state if selected else 'unavailable',
        'current_instance_selected': bool(selected and selected.instance.id == current_instance_id),
        'candidates': candidates,
    }
