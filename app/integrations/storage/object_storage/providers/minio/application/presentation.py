from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import aliased

from app.common.pagination import paginate_sequence, paginate_query
from app.common.presentation import present_user_datetime
from app.extensions.db import db
from app.integrations.asset_owner_sources import paginate_bound_observability_source_rows
from app.integrations.deletion import asset_owner_deletion_guard
from app.integrations.observability.metrics_source.providers import provider_definition
from app.integrations.runtime.presentation import runtime_history_view, runtime_observation_state_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.storage.object_storage.providers.minio.application.service import (
    alert_source_for_binding,
    current_alert_binding,
    current_metrics_binding,
    metrics_source_for_binding,
)
from app.integrations.storage.object_storage.providers.minio.capabilities import API_CAPABILITIES, CAPABILITY_PROFILE
from app.integrations.storage.object_storage.providers.minio.compatibility import compatibility_policy_view
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.minio import MinioInstance
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem


@dataclass(frozen=True, slots=True)
class MinioIndexQuery:
    tab: str = 'coverage'
    query: str = ''
    environment: str = ''
    readiness: str = ''
    compatibility: str = ''
    page: int = 1
    per_page: int = 5
    coverage_query: str = ''
    coverage_environment: str = ''
    coverage_status: str = ''
    coverage_page: int = 1
    coverage_per_page: int = 5


@dataclass(frozen=True, slots=True)
class MinioDetailQuery:
    capability_query: str = ''
    capability_requirement: str = ''
    capability_status: str = ''
    capability_page: int = 1
    capability_per_page: int = 5
    binding_page: int = 1
    binding_per_page: int = 5
    history_page: int = 1
    history_per_page: int = 5
    history_trigger: str = ''
    history_health: str = ''
    history_readiness: str = ''


def _active_source_exists(integration_type: str, *, source_name: str | None = None):
    source = aliased(IntegrationInstance)
    condition = [
        IntegrationBinding.asset_type == 'object_storage_system',
        IntegrationBinding.asset_key == MinioInstance.object_storage_system_id,
        IntegrationBinding.binding_role == 'primary',
        IntegrationBinding.enabled.is_(True),
        source.enabled.is_(True),
        source.integration_type == integration_type,
    ]
    if source_name:
        condition.append(source.name.ilike(source_name))
    return (
        select(IntegrationBinding.id)
        .join(source, source.id == IntegrationBinding.integration_instance_id)
        .where(*condition)
        .exists()
    )


def _minio_index_base_query():
    return (
        MinioInstance.query.join(MinioInstance.integration_instance)
        .join(MinioInstance.object_storage_system)
    )


def _index_registry_query(query: MinioIndexQuery):
    rows = _minio_index_base_query()
    if query.query:
        term = f'%{query.query}%'
        rows = rows.filter(or_(
            IntegrationInstance.name.ilike(term),
            ObjectStorageSystem.name.ilike(term),
            IntegrationInstance.environment.ilike(term),
            MinioInstance.compatibility_profile.ilike(term),
            MinioInstance.declared_release.ilike(term),
        ))
    if query.environment:
        rows = rows.filter(IntegrationInstance.environment == query.environment)
    if query.readiness:
        rows = rows.filter(IntegrationInstance.readiness_status == query.readiness)
    if query.compatibility:
        rows = rows.filter(MinioInstance.compatibility_profile == query.compatibility)
    return rows.order_by(IntegrationInstance.name.asc(), MinioInstance.id.asc())


def _index_coverage_query(query: MinioIndexQuery, *, metrics_exists, alerts_exists):
    rows = _minio_index_base_query()
    if query.coverage_query:
        term = f'%{query.coverage_query}%'
        rows = rows.filter(or_(
            IntegrationInstance.name.ilike(term),
            ObjectStorageSystem.name.ilike(term),
            IntegrationInstance.environment.ilike(term),
            _active_source_exists('metrics_source', source_name=term),
            _active_source_exists('alert_source', source_name=term),
        ))
    if query.coverage_environment:
        rows = rows.filter(IntegrationInstance.environment == query.coverage_environment)
    covered = and_(IntegrationInstance.readiness_status == 'ready', metrics_exists, alerts_exists)
    if query.coverage_status == 'ready':
        rows = rows.filter(covered)
    elif query.coverage_status == 'attention':
        rows = rows.filter(~covered)
    return rows.order_by(IntegrationInstance.name.asc(), MinioInstance.id.asc())


def _minio_portfolio_stats(*, metrics_exists, alerts_exists) -> dict[str, int]:
    covered = and_(IntegrationInstance.readiness_status == 'ready', metrics_exists, alerts_exists)
    total, ready, metrics, alerts, covered_count = (
        db.session.query(
            func.count(MinioInstance.id),
            func.sum(case((IntegrationInstance.readiness_status == 'ready', 1), else_=0)),
            func.sum(case((metrics_exists, 1), else_=0)),
            func.sum(case((alerts_exists, 1), else_=0)),
            func.sum(case((covered, 1), else_=0)),
        )
        .select_from(MinioInstance)
        .join(MinioInstance.integration_instance)
        .one()
    )
    total = int(total or 0)
    ready = int(ready or 0)
    metrics = int(metrics or 0)
    alerts = int(alerts or 0)
    return {
        'total': total,
        'configured': total,
        'ready': ready,
        'attention': total - ready,
        'bindings': metrics + alerts,
        'metrics_bound': metrics,
        'alerts_bound': alerts,
        'uncovered': total - int(covered_count or 0),
    }


def build_index_context(query: MinioIndexQuery | None = None) -> dict[str, Any]:
    query = query or MinioIndexQuery()
    metrics_exists = _active_source_exists('metrics_source')
    alerts_exists = _active_source_exists('alert_source')
    stats = _minio_portfolio_stats(metrics_exists=metrics_exists, alerts_exists=alerts_exists)
    registry_instances, pagination = paginate_query(
        _index_registry_query(query), page=query.page, per_page=query.per_page
    )
    coverage_instances, coverage_pagination = paginate_query(
        _index_coverage_query(query, metrics_exists=metrics_exists, alerts_exists=alerts_exists),
        page=query.coverage_page, per_page=query.coverage_per_page,
    )

    registry_rows: list[dict[str, Any]] = []
    for instance in registry_instances:
        metrics_binding = current_metrics_binding(instance)
        alert_binding = current_alert_binding(instance)
        registry_rows.append({
            'id': instance.id,
            'name': instance.name,
            'environment': instance.environment,
            'endpoint': instance.endpoint,
            'asset_name': instance.object_storage_system.name,
            'readiness_status': instance.readiness_status or 'validation_required',
            'compatibility_profile': instance.compatibility_profile,
            'declared_release': instance.declared_release,
            'metrics_status': _source_binding_status(metrics_source_for_binding(metrics_binding), metrics_binding),
            'alert_status': _source_binding_status(alert_source_for_binding(alert_binding), alert_binding),
            'binding_count': int(metrics_binding is not None) + int(alert_binding is not None),
        })

    coverage_rows: list[dict[str, Any]] = []
    for instance in coverage_instances:
        metrics_binding = current_metrics_binding(instance)
        metrics_source = metrics_source_for_binding(metrics_binding)
        alert_binding = current_alert_binding(instance)
        alert_source = alert_source_for_binding(alert_binding)
        uncovered = metrics_binding is None or alert_binding is None
        attention = uncovered or instance.readiness_status != 'ready'
        coverage_rows.append({
            'asset_name': instance.object_storage_system.name,
            'environment': instance.environment,
            'instance': instance,
            'api_status': _provider_status(instance),
            'metrics_source': metrics_source,
            'metrics_source_label': _metrics_source_label(metrics_source),
            'metrics_status': _source_binding_status(metrics_source, metrics_binding),
            'alert_source': alert_source,
            'alert_status': _source_binding_status(alert_source, alert_binding),
            'coverage_status': 'attention' if attention else 'ready',
            'coverage_label': 'Attention' if attention else 'Ready',
        })

    all_environments = [
        value for (value,) in db.session.query(IntegrationInstance.environment)
        .join(MinioInstance, MinioInstance.integration_instance_id == IntegrationInstance.id)
        .distinct().all() if value
    ]
    compatibility_options = [
        value for (value,) in db.session.query(MinioInstance.compatibility_profile)
        .distinct().all() if value
    ]
    return {
        'rows': registry_rows,
        'coverage_rows': coverage_rows,
        'pagination': pagination,
        'coverage_pagination': coverage_pagination,
        'active_tab': query.tab if query.tab in {'coverage', 'registry'} else 'coverage',
        'selected_query': query.query,
        'selected_environment': query.environment,
        'selected_readiness': query.readiness,
        'selected_compatibility': query.compatibility,
        'selected_coverage_query': query.coverage_query,
        'selected_coverage_environment': query.coverage_environment,
        'selected_coverage_status': query.coverage_status,
        'registry_has_active_filters': bool(
            query.query or query.environment or query.readiness or query.compatibility
        ),
        'coverage_has_active_filters': bool(
            query.coverage_query or query.coverage_environment or query.coverage_status
        ),
        'environment_options': sorted(all_environments),
        'readiness_options': [
            {'value': 'ready', 'label': 'Ready'},
            {'value': 'blocked', 'label': 'Blocked'},
            {'value': 'validation_required', 'label': 'Validation Required'},
        ],
        'compatibility_options': sorted(compatibility_options),
        'coverage_environment_options': sorted(all_environments),
        'coverage_status_options': [
            {'value': 'ready', 'label': 'Ready'},
            {'value': 'attention', 'label': 'Attention'},
        ],
        'stats': stats,
    }


def _metrics_source_label(source: object | None) -> str:
    if source is None:
        return 'No Metrics Source Binding'
    provider_key = str(getattr(source, 'provider_key', None) or '').strip().lower()
    return provider_definition(provider_key).label if provider_key else 'Metrics Source'


def build_detail_context(
    instance: MinioInstance,
    query: MinioDetailQuery | None = None,
) -> dict[str, Any]:
    query = query or MinioDetailQuery()
    metrics_binding = current_metrics_binding(instance)
    metrics_source = metrics_source_for_binding(metrics_binding)
    alert_binding = current_alert_binding(instance)
    alert_source = alert_source_for_binding(alert_binding)

    runtime_rows, runtime_pagination = paginate_runtime_history(
        'object_storage',
        str(instance.id),
        page=query.history_page,
        per_page=query.history_per_page,
        trigger_type=query.history_trigger,
        health_status=query.history_health,
        readiness=query.history_readiness,
    )
    latest_rows, _latest_pagination = paginate_runtime_history(
        'object_storage',
        str(instance.id),
        page=1,
        per_page=5,
    )
    latest_runtime = latest_rows[0] if latest_rows else None
    runtime_state = runtime_observation_state_view(
        latest_runtime,
        fallback_readiness=instance.readiness_status or 'validation_required',
        fallback_compatibility_profile=instance.compatibility_profile,
        fallback_capabilities=tuple(instance.capabilities or ()),
    )

    binding_rows, binding_pagination = paginate_bound_observability_source_rows(
        asset_type='object_storage_system',
        asset_key=instance.object_storage_system_id,
        page=query.binding_page,
        per_page=query.binding_per_page,
    )
    capability_registry = build_minio_capability_registry(
        instance,
        query=query.capability_query,
        requirement=query.capability_requirement,
        status=query.capability_status,
        page=query.capability_page,
        per_page=query.capability_per_page,
    )

    inventory_observed_at = instance.object_storage_system.inventory_observed_at
    source_metadata = instance.integration_instance.metadata_json or {}
    source_changed = inventory_observed_at is not None and (
        int(source_metadata.get('object_storage_connection_generation') or 0)
        != int(source_metadata.get('object_storage_inventory_generation') or 0)
    )
    inventory_current = inventory_observed_at is not None and not source_changed

    return {
        'instance': instance,
        'asset': instance.object_storage_system,
        'canonical': instance.integration_instance,
        'runtime_state': runtime_state,
        'runtime_history': runtime_history_view(runtime_rows, pagination=runtime_pagination),
        'metrics_binding': metrics_binding,
        'metrics_source': metrics_source,
        'metrics_status': _source_binding_status(metrics_source, metrics_binding),
        'alert_binding': alert_binding,
        'alert_source': alert_source,
        'alert_status': _source_binding_status(alert_source, alert_binding),
        'binding_rows': binding_rows,
        'binding_total': binding_pagination['total_items'],
        'binding_pagination': binding_pagination,
        'capability_registry': capability_registry,
        'compatibility_policy': compatibility_policy_view(
            instance.detected_product or 'minio', instance.declared_release
        ),
        'validated_at_display': present_user_datetime(instance.last_validated_at, empty='Not validated'),
        'checked_at_display': present_user_datetime(instance.last_checked_at, empty='Not observed'),
        'bucket_count': ObjectStorageBucket.query.filter_by(
            object_storage_system_id=instance.object_storage_system_id
        ).count(),
        'inventory_status': 'ready' if inventory_current else 'unknown',
        'inventory_status_label': (
            'Current Source Snapshot' if inventory_current
            else 'Source Changed · Sync Required' if source_changed and inventory_observed_at
            else 'No Committed Inventory'
        ),
        'inventory_source_changed': source_changed,
        'inventory_current': inventory_current,
        'inventory_observed_at_display': present_user_datetime(
            inventory_observed_at,
            empty='Not Collected',
        ),
        'capability_count': len(instance.capabilities or ()),
        'deletion_guard': asset_owner_deletion_guard(
            integration_type='object_storage',
            integration_instance_id=instance.integration_instance_id,
            asset_type='object_storage_system',
            asset_key=str(instance.object_storage_system_id),
        ),
    }


def build_minio_capability_registry(
    instance: MinioInstance,
    *,
    query: str = '',
    requirement: str = '',
    status: str = '',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    observed = set(instance.capabilities or ())
    rows: list[dict[str, Any]] = []
    for definition in API_CAPABILITIES:
        available = definition.key in observed
        if available:
            row_status = 'ready'
        elif definition.required and instance.last_validated_at:
            row_status = 'blocked'
        else:
            row_status = 'not_checked'
        rows.append(
            {
                'key': definition.key,
                'label': definition.label,
                'description': definition.description,
                'required': bool(definition.required),
                'requirement_label': 'Required' if definition.required else 'Optional',
                'status': row_status,
                'status_label': {
                    'ready': 'Ready',
                    'blocked': 'Blocked',
                    'not_checked': 'Not Checked',
                }[row_status],
                'available': available,
                'contract': CAPABILITY_PROFILE,
                'category': 'MinIO S3 API',
                'source_owner': 'MinIO S3 API',
                'evidence': (
                    f'Full Validation observed {definition.label} in the persisted MinIO capability snapshot.'
                    if available
                    else (
                        f'Full Validation did not prove required {definition.label}.'
                        if row_status == 'blocked'
                        else (
                            f'{definition.label} has no validated provider-core evidence. '
                            'Optional bucket configuration is assessed during Inventory Sync.'
                        )
                    )
                ),
                'success_criteria': definition.description,
                'impact': (
                    'Required provider capability used to establish MinIO readiness.'
                    if definition.required
                    else 'Optional read-only capability that increases object-storage governance depth.'
                ),
                'next_action': (
                    'No corrective action is required. Revalidate after MinIO upgrades or credential changes.'
                    if available
                    else (
                        'Verify the registered S3 API access and rerun Full Validation.'
                        if row_status == 'blocked'
                        else (
                            'Review optional bucket evidence after Object Storage Inventory Sync; '
                            'do not infer provider-core readiness from an untested API.'
                        )
                    )
                ),
                'remediation': (
                    []
                    if available
                    else (
                        [
                            'Verify the registered MinIO endpoint and required S3 discovery permissions.',
                            'Rerun Full Validation and confirm this capability becomes Ready.',
                        ]
                        if row_status == 'blocked'
                        else []
                    )
                ),
                'technical_checks': [],
            }
        )

    normalized_query = str(query or '').strip().lower()
    normalized_requirement = str(requirement or '').strip().lower()
    normalized_status = str(status or '').strip().lower()
    if normalized_query:
        rows = [
            row
            for row in rows
            if normalized_query
            in ' '.join(
                str(value or '') for value in (row['key'], row['label'], row['description'], row['contract'])
            ).lower()
        ]
    if normalized_requirement in {'required', 'optional'}:
        want_required = normalized_requirement == 'required'
        rows = [row for row in rows if row['required'] is want_required]
    else:
        normalized_requirement = ''
    if normalized_status in {'ready', 'blocked', 'not_checked'}:
        rows = [row for row in rows if row['status'] == normalized_status]
    else:
        normalized_status = ''

    page_rows, pagination = paginate_sequence(rows, page=page, per_page=per_page)
    return {
        'rows': page_rows,
        'pagination': pagination,
        'filters': {
            'query': normalized_query,
            'requirement': normalized_requirement,
            'status': normalized_status,
        },
        'total_contracts': len(API_CAPABILITIES),
        'ready_count': len(observed.intersection({item.key for item in API_CAPABILITIES})),
        'required_count': sum(1 for item in API_CAPABILITIES if item.required),
        'optional_count': sum(1 for item in API_CAPABILITIES if not item.required),
    }


def _provider_status(instance: MinioInstance) -> dict[str, str]:
    readiness = instance.readiness_status or 'validation_required'
    if readiness == 'ready':
        return {'status': 'ready', 'label': 'Ready'}
    if readiness == 'blocked':
        return {'status': 'blocked', 'label': 'Blocked'}
    return {'status': 'validation_required', 'label': 'Validation Required'}


def _source_binding_status(source: Any | None, binding: IntegrationBinding | None) -> dict[str, str]:
    if source is None or binding is None:
        return {'status': 'not_configured', 'label': 'Not Bound'}
    if source.readiness_status == 'ready' and binding.validation_status == 'ready':
        return {'status': 'ready', 'label': 'Ready'}
    if binding.validation_status == 'blocked' or source.readiness_status == 'blocked':
        return {'status': 'blocked', 'label': 'Blocked'}
    return {'status': 'degraded', 'label': 'Validation Required'}


def _paginate(rows: list[dict[str, Any]], *, page: int, per_page: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
