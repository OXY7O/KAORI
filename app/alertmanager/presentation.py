from __future__ import annotations

import re
from typing import Any

from app.integrations.alertmanager.capabilities import CAPABILITIES, CAPABILITY_BY_KEY
from app.alertmanager.repository import count_bindings_by_scope_type, list_bindings_for_instance, list_instances
from app.integrations.alertmanager.requirements import evaluate_module_readiness
from app.alertmanager.resolver import AlertmanagerSourceResolution, resolve_alertmanager_sources
from app.integrations.registry import get_integration
from app.alertmanager.sanitization import safe_endpoint
from app.common.presentation import present_user_datetime
from app.extensions import db
from app.integrations.binding_selectors import selector_form_values, selector_is_configured, selector_summary
from app.integrations.deletion import provider_deletion_guard
from app.integrations.coverage import build_provider_coverage
from app.integrations.runtime.presentation import runtime_history_view, runtime_state_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding
from app.models.cluster import Cluster
from app.integrations.readiness import resolve_binding_operational_status


def build_inventory_context(
    *,
    query: str = '',
    compatibility: str = '',
    readiness: str = '',
    deployment_type: str = '',
    tab: str = 'coverage',
    page: int = 1,
    per_page: int = 5,
    coverage_query: str = '',
    coverage_environment: str = '',
    coverage_status: str = '',
    coverage_page: int = 1,
    coverage_per_page: int = 5,
) -> dict[str, Any]:
    instances = list_instances()
    rows = [_instance_row(instance) for instance in instances]
    filtered = rows
    normalized_query = query.strip().lower()
    if normalized_query:
        filtered = [
            row
            for row in filtered
            if normalized_query in row['search_text']
        ]
    if readiness:
        filtered = [row for row in filtered if row['readiness'] == readiness]
    if compatibility:
        filtered = [row for row in filtered if row['compatibility'] == compatibility]
    if deployment_type:
        filtered = [row for row in filtered if row['deployment_type'] == deployment_type]

    page_rows, pagination = _paginate(filtered, page=page, per_page=per_page)
    stats = {
        'total': len(rows),
        'configured': sum(1 for row in rows if row['configured']),
        'ready': sum(1 for row in rows if row['readiness'] == 'ready'),
        'attention': sum(1 for row in rows if row['configured'] and row['readiness'] != 'ready'),
        'bindings': sum(row['binding_count'] for row in rows),
    }
    coverage_context = build_provider_coverage(
        'alertmanager',
        page=coverage_page,
        per_page=coverage_per_page,
        query=coverage_query,
        environment=coverage_environment,
        status=coverage_status,
    )
    return {
        'rows': page_rows,
        'stats': stats,
        'pagination': pagination,
        'active_tab': tab if tab in {'coverage', 'registry'} else 'coverage',
        'selected_query': query,
        'selected_compatibility': compatibility,
        'selected_readiness': readiness,
        'selected_deployment_type': deployment_type,
        'readiness_options': sorted({row['readiness'] for row in rows}),
        'compatibility_options': sorted({row['compatibility'] for row in rows}),
        'deployment_type_options': sorted({row['deployment_type'] for row in rows}),
        'binding_scope_counts': count_bindings_by_scope_type(),
        **coverage_context,
    }


def _alertmanager_request_target(endpoint: str, probe: str) -> str:
    match = re.search(r'GET\s+(/api/v2/[A-Za-z0-9_./-]+)', probe or '')
    if not match:
        return probe or 'No provider request recorded.'
    path = match.group(1).rstrip('.,')
    base = str(endpoint or '').rstrip('/')
    return f'GET {base}{path}' if base else f'GET {path}'


def build_instance_context(instance: AlertmanagerInstance | None = None) -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()
    bindings = list_bindings_for_instance(instance.id) if instance else []
    observed_capabilities = set(instance.capabilities or []) if instance else set()
    capability_rows = []
    for capability in CAPABILITIES:
        available = capability.key in observed_capabilities
        evidence = (
            'Observed during the latest Full Validation.'
            if available
            else 'Not observed in the latest Full Validation evidence.'
        )
        request_target = _alertmanager_request_target(instance.endpoint if instance else '', capability.probe)
        capability_rows.append({
            'key': capability.key,
            'label': capability.label,
            'category': capability.category,
            'description': capability.description,
            'required': capability.required,
            'available': available,
            'status_label': 'Observed' if available else ('Required missing' if capability.required else 'Not observed'),
            'status_tone': 'normal' if available else ('critical' if capability.required else 'warning'),
            'status_icon': 'circle-check' if available else ('octagon-alert' if capability.required else 'triangle-alert'),
            'probe': (
                f'KAORI checks this capability to confirm that the configured Alertmanager source can support '
                f'{capability.impact.rstrip(".").lower()}. Exact request targets are available under Technical Checks.'
            ),
            'technical_checks': [{
                'label': 'Alertmanager API Request',
                'status': 'available' if available else 'not_observed',
                'status_label': 'Ready' if available else 'Not Observed',
                'evidence': evidence,
                'query': request_target,
                'registered_query': request_target,
                'series_count_display': '',
                'value_summary': '',
                'error_detail': '',
                'tone': 'normal' if available else 'warning',
                'icon': 'circle-check' if available else 'triangle-alert',
            }],
            'success_criteria': capability.success_criteria,
            'configuration_guidance': capability.configuration_guidance,
            'impact': capability.impact,
            'remediation': list(capability.remediation),
            'evidence': evidence,
            'next_action': (
                'No immediate change is required. Revalidate after connection, proxy, authentication, or alert payload changes.'
                if available
                else capability.remediation[0] if capability.remediation else 'Review the integration configuration and rerun Full Validation.'
            ),
        })
    deletion_guard = (
        provider_deletion_guard(provider_type='alertmanager', provider_instance_id=instance.id)
        if instance is not None
        else None
    )
    return {
        'instance': instance,
        'bindings': bindings,
        'deletion_guard': deletion_guard,
        'binding_rows': [_binding_row(binding, instance) for binding in bindings],
        'clusters': clusters,
        'capability_rows': capability_rows,
        'module_readiness_rows': evaluate_module_readiness(observed_capabilities),
        'capability_summary': {
            'total': len(CAPABILITIES),
            'observed': len(observed_capabilities.intersection(CAPABILITY_BY_KEY)),
            'required_missing': sum(1 for capability in CAPABILITIES if capability.required and capability.key not in observed_capabilities),
            'optional_missing': sum(1 for capability in CAPABILITIES if not capability.required and capability.key not in observed_capabilities),
        },
        'source_resolution_rows': _source_resolution_rows(instance) if instance else [],
        'runtime_state': runtime_state_view(get_integration('alertmanager').adapter.get_state(instance)) if instance else None,
        'runtime_history': build_runtime_history_context(instance) if instance else None,
        'scope_type_labels': {
            'kubernetes_cluster': 'Managed cluster',
            'server': 'Infrastructure asset',
            'server_group': 'Infrastructure asset group',
            'hci_environment': 'Platform environment',
            'storage_service': 'Infrastructure service',
            'global': 'Global operational scope',
        },
        'stats': {
            'bindings': len(bindings),
            'ready': bool(instance and instance.readiness_status == 'ready'),
            'capabilities': len(observed_capabilities),
        },
    }


def _instance_row(instance: AlertmanagerInstance) -> dict[str, Any]:
    readiness = instance.readiness_status or ('validation_required' if instance.endpoint else 'not_configured')
    return {
        'instance': instance,
        'configured': bool(instance.endpoint),
        'endpoint': safe_endpoint(instance.endpoint),
        'version': instance.detected_version,
        'compatibility': instance.compatibility_status or 'validation_required',
        'readiness': readiness,
        'profile': instance.compatibility_profile,
        'deployment_type': instance.deployment_type,
        'validated_at': present_user_datetime(instance.last_validated_at, empty='Not validated'),
        'binding_count': len(list_bindings_for_instance(instance.id)),
        'scope_types': sorted({binding.asset_type for binding in list_bindings_for_instance(instance.id) if binding.enabled}),
        'search_text': ' '.join(
            filter(
                None,
                [
                    instance.name.lower(),
                    (instance.description or '').lower(),
                    (instance.endpoint or '').lower(),
                    (instance.deployment_type or '').lower(),
                    (instance.detected_version or '').lower(),
                    (instance.compatibility_profile or '').lower(),
                ],
            )
        ),
    }


def _binding_row(binding: IntegrationBinding, source: AlertmanagerInstance) -> dict[str, Any]:
    label = binding.asset_key
    if binding.asset_type == 'kubernetes_cluster':
        cluster = db.session.get(Cluster, binding.asset_key)
        if cluster is not None:
            label = cluster.name
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
        'scope_label': label,
        'scope_type_label': binding.asset_type.replace('_', ' ').title(),
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


def _paginate(
    rows: list[dict[str, Any]],
    *,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed = [5, 10, 25, 50]
    if per_page not in allowed:
        per_page = 5
    total_items = len(rows)
    total_pages = max((total_items + per_page - 1) // per_page, 1)
    page = min(max(page, 1), total_pages)
    start = (page - 1) * per_page
    end = start + per_page
    return rows[start:end], {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'start_item': start + 1 if total_items else 0,
        'end_item': min(end, total_items),
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
        'allowed_per_page': allowed,
    }


def _source_resolution_rows(instance: AlertmanagerInstance) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_scopes: set[tuple[str, str]] = set()
    for binding in list_bindings_for_instance(instance.id):
        scope = (binding.asset_type, binding.asset_key)
        if scope in seen_scopes:
            continue
        seen_scopes.add(scope)
        alerts_resolution = resolve_alertmanager_sources(
            scope_type=binding.asset_type,
            scope_key=binding.asset_key,
            required_capabilities=('alerts_v2',),
        )
        silences_resolution = resolve_alertmanager_sources(
            scope_type=binding.asset_type,
            scope_key=binding.asset_key,
            required_capabilities=('silences_v2',),
        )
        rows.append({
            'scope_type': binding.asset_type,
            'scope_type_label': binding.asset_type.replace('_', ' ').title(),
        'selector_summary': selector_summary(binding.selector_json),
        'selector_configured': selector_is_configured(binding.selector_json),
        'validation_status': binding.validation_status or 'validation_required',
            'scope_key': binding.asset_key,
            'scope_label': _scope_label(binding.asset_type, binding.asset_key),
            'alerts': _resolution_view(alerts_resolution, current_instance_id=instance.id),
            'silences': _resolution_view(silences_resolution, current_instance_id=instance.id),
        })
    return rows


def _resolution_view(
    resolution: AlertmanagerSourceResolution,
    *,
    current_instance_id: int,
) -> dict[str, Any]:
    selected = resolution.selected
    return {
        'selected_instance_id': selected.instance.id if selected else None,
        'selected_instance_name': selected.instance.name if selected else None,
        'selected_role': selected.binding.binding_role if selected else None,
        'selected_operational_state': selected.operational_state if selected else 'unavailable',
        'current_instance_selected': bool(selected and selected.instance.id == current_instance_id),
        'required_capabilities': [
            CAPABILITY_BY_KEY[key].label if key in CAPABILITY_BY_KEY else key
            for key in resolution.required_capabilities
        ],
        'candidates': [
            {
                **candidate.to_dict(),
                'is_selected': bool(selected and candidate.binding.id == selected.binding.id),
                'is_current_instance': candidate.instance.id == current_instance_id,
                'missing_capability_labels': [
                    CAPABILITY_BY_KEY[key].label if key in CAPABILITY_BY_KEY else key
                    for key in candidate.missing_capabilities
                ],
            }
            for candidate in resolution.candidates
        ],
    }


def _scope_label(scope_type: str, scope_key: str) -> str:
    if scope_type == 'kubernetes_cluster':
        cluster = db.session.get(Cluster, scope_key)
        if cluster is not None:
            return cluster.name
    return scope_key


def build_runtime_history_context(
    instance: AlertmanagerInstance,
    *,
    page: int = 1,
    per_page: int = 5,
) -> dict[str, object]:
    rows, pagination = paginate_runtime_history(
        'alertmanager',
        str(instance.id),
        page=page,
        per_page=per_page,
    )
    return runtime_history_view(rows, pagination=pagination)
