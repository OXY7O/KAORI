from __future__ import annotations

import re
from typing import Any

from sqlalchemy import case, func, or_

from app.common.pagination import paginate_query, paginate_sequence
from app.common.presentation import present_user_datetime
from app.extensions.db import db
from app.integrations.binding_selectors import selector_form_values, selector_is_configured, selector_summary
from app.integrations.consumer_assets import build_consumer_asset_groups
from app.integrations.coverage import build_provider_coverage
from app.integrations.deletion import provider_deletion_guard
from app.integrations.kernel.registry import get_integration
from app.integrations.observability.alert_source.providers.alertmanager.application.repository import (
    count_bindings_by_scope_type,
)
from app.integrations.observability.alert_source.providers.alertmanager.application.resolver import (
    AlertmanagerSourceResolution,
    resolve_alertmanager_sources,
)
from app.integrations.observability.alert_source.providers.alertmanager.application.sanitization import safe_endpoint
from app.integrations.observability.alert_source.providers.alertmanager.binding_profiles import (
    get_alert_consumer_profile,
)
from app.integrations.observability.alert_source.providers.alertmanager.capabilities import (
    CAPABILITY_BY_KEY,
    CORE_CAPABILITIES,
)
from app.integrations.observability.alert_source.providers.alertmanager.requirements import evaluate_module_readiness
from app.integrations.readiness import resolve_binding_operational_status
from app.integrations.runtime.presentation import runtime_history_view, runtime_state_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.models.alertmanager import AlertmanagerInstance
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.object_storage import ObjectStorageSystem


def build_inventory_context(
    *,
    query: str = '',
    compatibility: str = '',
    readiness: str = '',
    tab: str = 'coverage',
    page: int = 1,
    per_page: int = 5,
    coverage_query: str = '',
    coverage_environment: str = '',
    coverage_status: str = '',
    coverage_page: int = 1,
    coverage_per_page: int = 5,
) -> dict[str, Any]:
    configured = (AlertmanagerInstance.endpoint.is_not(None)) & (AlertmanagerInstance.endpoint != '')
    readiness_key = func.coalesce(IntegrationInstance.readiness_status, 'validation_required')
    totals = (
        db.session.query(
            func.count(AlertmanagerInstance.id),
            func.sum(case((configured, 1), else_=0)),
            func.sum(case((readiness_key == 'ready', 1), else_=0)),
            func.sum(case((configured & (readiness_key != 'ready'), 1), else_=0)),
        )
        .join(AlertmanagerInstance.integration_instance)
        .one()
    )
    binding_total = int(
        db.session.query(func.count(IntegrationBinding.id))
        .join(IntegrationInstance)
        .filter(IntegrationInstance.integration_type == 'alert_source')
        .scalar() or 0
    )
    stats = {
        'total': int(totals[0] or 0),
        'configured': int(totals[1] or 0),
        'ready': int(totals[2] or 0),
        'attention': int(totals[3] or 0),
        'bindings': binding_total,
    }
    registry = AlertmanagerInstance.query.join(AlertmanagerInstance.integration_instance)
    if query.strip():
        term = f'%{query.strip()}%'
        registry = registry.filter(or_(
            IntegrationInstance.name.ilike(term),
            IntegrationInstance.description.ilike(term),
            AlertmanagerInstance.endpoint.ilike(term),
            AlertmanagerInstance.detected_version.ilike(term),
            AlertmanagerInstance.compatibility_profile.ilike(term),
        ))
    if readiness:
        registry = registry.filter(readiness_key == readiness)
    if compatibility:
        registry = registry.filter(
            func.coalesce(AlertmanagerInstance.compatibility_status, 'validation_required') == compatibility
        )
    registry = registry.order_by(IntegrationInstance.name.asc(), AlertmanagerInstance.id.asc())
    page_instances, pagination = paginate_query(registry, page=page, per_page=per_page)
    canonical_ids = [instance.integration_instance_id for instance in page_instances]
    visible_bindings = (
        db.session.query(
            IntegrationBinding.integration_instance_id,
            IntegrationBinding.asset_type,
            IntegrationBinding.enabled,
        )
        .filter(IntegrationBinding.integration_instance_id.in_(canonical_ids))
        .all()
        if canonical_ids else []
    )
    binding_summary: dict[int, tuple[int, set[str]]] = {
        identity: (0, set()) for identity in canonical_ids
    }
    for identity, asset_type, enabled in visible_bindings:
        count, asset_types = binding_summary[identity]
        if enabled:
            asset_types.add(asset_type)
        binding_summary[identity] = (count + 1, asset_types)
    page_rows = [_instance_row(instance, binding_summary=binding_summary) for instance in page_instances]
    readiness_options = sorted({
        value or 'validation_required'
        for (value,) in db.session.query(IntegrationInstance.readiness_status)
        .join(AlertmanagerInstance, AlertmanagerInstance.integration_instance_id == IntegrationInstance.id)
        .distinct().all()
    })
    compatibility_options = sorted({
        value or 'validation_required'
        for (value,) in db.session.query(AlertmanagerInstance.compatibility_status).distinct().all()
    })
    coverage_context = build_provider_coverage(
        'alert_source',
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
        'readiness_options': readiness_options,
        'compatibility_options': compatibility_options,
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


def _core_capability_summary(observed_capabilities: set[str]) -> dict[str, int]:
    return {
        'total': len(CORE_CAPABILITIES),
        'observed': sum(1 for capability in CORE_CAPABILITIES if capability.key in observed_capabilities),
        'required_missing': sum(
            1 for capability in CORE_CAPABILITIES if capability.required and capability.key not in observed_capabilities
        ),
        'optional_missing': sum(
            1
            for capability in CORE_CAPABILITIES
            if not capability.required and capability.key not in observed_capabilities
        ),
    }


def build_instance_context(
    instance: AlertmanagerInstance | None = None,
    *,
    binding_page: int = 1,
    binding_per_page: int = 5,
) -> dict[str, Any]:
    consumer_asset_groups = build_consumer_asset_groups(get_alert_consumer_profile)
    binding_query = IntegrationBinding.query.filter_by(
        integration_instance_id=instance.integration_instance_id,
    ).order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc()) if instance else None
    bindings, binding_registry_pagination = (
        paginate_query(binding_query, page=binding_page, per_page=binding_per_page)
        if binding_query is not None else paginate_sequence([], page=binding_page, per_page=binding_per_page)
    )
    binding_total = binding_registry_pagination['total_items']
    observed_capabilities = set(instance.capabilities or []) if instance else set()
    capability_rows = []
    for capability in CORE_CAPABILITIES:
        available = capability.key in observed_capabilities
        evidence = (
            'Observed during the latest Full Validation.'
            if available
            else 'Not observed in the latest Full Validation evidence.'
        )
        request_target = _alertmanager_request_target(instance.endpoint if instance else '', capability.probe)
        capability_rows.append(
            {
                'key': capability.key,
                'label': capability.label,
                'category': capability.category,
                'description': capability.description,
                'required': capability.required,
                'available': available,
                'status_label': 'Observed'
                if available
                else ('Required missing' if capability.required else 'Not observed'),
                'status_tone': 'normal' if available else ('critical' if capability.required else 'warning'),
                'status_icon': 'circle-check'
                if available
                else ('octagon-alert' if capability.required else 'triangle-alert'),
                'probe': (
                    f'KAORI checks this capability to confirm that the configured Alertmanager source can support '
                    f'{capability.impact.rstrip(".").lower()}. Exact request targets are available under Technical Checks.'
                ),
                'technical_checks': [
                    {
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
                    }
                ],
                'success_criteria': capability.success_criteria,
                'configuration_guidance': capability.configuration_guidance,
                'impact': capability.impact,
                'remediation': list(capability.remediation),
                'evidence': evidence,
                'next_action': (
                    'No immediate change is required. Revalidate after connection, proxy, authentication, or alert payload changes.'
                    if available
                    else capability.remediation[0]
                    if capability.remediation
                    else 'Review the integration configuration and rerun Full Validation.'
                ),
            }
        )
    deletion_guard = (
        provider_deletion_guard(
            integration_type='alert_source', integration_instance_id=instance.integration_instance_id
        )
        if instance is not None
        else None
    )
    binding_rows = [_binding_row(binding, instance) for binding in bindings] if instance is not None else []
    binding_registry_rows = binding_rows
    return {
        'instance': instance,
        'bindings': bindings,
        'deletion_guard': deletion_guard,
        'binding_rows': binding_rows,
        'binding_total': binding_total,
        'binding_registry_rows': binding_registry_rows,
        'binding_registry_pagination': binding_registry_pagination,
        'consumer_asset_groups': consumer_asset_groups,
        'capability_rows': capability_rows,
        'module_readiness_rows': evaluate_module_readiness(observed_capabilities),
        'capability_summary': _core_capability_summary(observed_capabilities),
        'source_resolution_rows': _source_resolution_rows(instance, bindings) if instance else [],
        'runtime_state': runtime_state_view(get_integration('alert_source').runtime_state(instance))
        if instance
        else None,
        'runtime_history': build_runtime_history_context(instance) if instance else None,
        'scope_type_labels': {
            'kubernetes_cluster': 'Managed cluster',
            'server': 'Infrastructure asset',
            'server_group': 'Infrastructure asset group',
            'hci_environment': 'Platform environment',
            'storage_service': 'Infrastructure service',
            'object_storage_system': 'Object storage system',
            'global': 'Global operational scope',
        },
        'stats': {
            'bindings': binding_total,
            'ready': bool(instance and instance.readiness_status == 'ready'),
            'capabilities': len(observed_capabilities),
        },
    }


def _instance_row(
    instance: AlertmanagerInstance, *, binding_summary: dict[int, tuple[int, set[str]]],
) -> dict[str, Any]:
    readiness = instance.readiness_status or ('validation_required' if instance.endpoint else 'not_configured')
    binding_count, scope_types = binding_summary.get(instance.integration_instance_id, (0, set()))
    return {
        'instance': instance,
        'configured': bool(instance.endpoint),
        'endpoint': safe_endpoint(instance.endpoint),
        'version': instance.detected_version,
        'compatibility': instance.compatibility_status or 'validation_required',
        'readiness': readiness,
        'profile': instance.compatibility_profile,
        'validated_at': present_user_datetime(instance.last_validated_at, empty='Not validated'),
        'binding_count': binding_count,
        'scope_types': sorted(scope_types),
        'search_text': ' '.join(
            filter(
                None,
                [
                    instance.name.lower(),
                    (instance.description or '').lower(),
                    (instance.endpoint or '').lower(),
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
    elif binding.asset_type == 'object_storage_system':
        asset = db.session.get(ObjectStorageSystem, binding.asset_key)
        if asset is not None:
            label = asset.name
    selector_values = selector_form_values(binding.selector_json)
    consumer_profile = get_alert_consumer_profile(binding.asset_type)
    validation_evidence = binding.validation_evidence or {}
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
        'validation_message': binding.validation_message or 'Run Binding Validation to establish consumer evidence.',
        'validation_evidence': validation_evidence,
        'last_validated_at': present_user_datetime(binding.last_validated_at, empty='Not validated'),
        'has_validation_result': bool(
            binding.last_validated_at or binding.validation_evidence or binding.validation_message
        ),
        'consumer_profile_key': binding.validation_profile
        or (consumer_profile.profile_key if consumer_profile else None),
        'consumer_profile_label': validation_evidence.get('profile_label')
        or (consumer_profile.label if consumer_profile else 'Unregistered Profile'),
        'matched_alerts': int(validation_evidence.get('matched_alerts') or 0),
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


def _source_resolution_rows(
    instance: AlertmanagerInstance, bindings: list[IntegrationBinding],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_scopes: set[tuple[str, str]] = set()
    for binding in bindings:
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
        consumer_profile = get_alert_consumer_profile(binding.asset_type)
        validation_evidence = binding.validation_evidence or {}
        rows.append(
            {
                'scope_type': binding.asset_type,
                'scope_type_label': binding.asset_type.replace('_', ' ').title(),
                'selector_summary': selector_summary(binding.selector_json),
                'selector_configured': selector_is_configured(binding.selector_json),
                'validation_status': binding.validation_status or 'validation_required',
                'consumer_profile_key': binding.validation_profile
                or (consumer_profile.profile_key if consumer_profile else None),
                'consumer_profile_label': validation_evidence.get('profile_label')
                or (consumer_profile.label if consumer_profile else 'Unregistered Profile'),
                'matched_alerts': int(validation_evidence.get('matched_alerts') or 0),
                'scope_key': binding.asset_key,
                'scope_label': _scope_label(binding.asset_type, binding.asset_key),
                'alerts': _resolution_view(alerts_resolution, current_instance_id=instance.id),
                'silences': _resolution_view(silences_resolution, current_instance_id=instance.id),
            }
        )
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
    if scope_type == 'object_storage_system':
        asset = db.session.get(ObjectStorageSystem, scope_key)
        if asset is not None:
            return asset.name
    return scope_key


def build_runtime_history_context(
    instance: AlertmanagerInstance,
    *,
    page: int = 1,
    per_page: int = 5,
    trigger_type: str = '',
    health_status: str = '',
    readiness: str = '',
) -> dict[str, object]:
    rows, pagination = paginate_runtime_history(
        'alert_source',
        str(instance.id),
        page=page,
        per_page=per_page,
        trigger_type=trigger_type,
        health_status=health_status,
        readiness=readiness,
    )
    return runtime_history_view(rows, pagination=pagination)
