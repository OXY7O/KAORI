from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.common.pagination import paginate_sequence
from app.common.presentation import present_user_datetime
from app.integrations.asset_owner_sources import build_bound_observability_source_rows
from app.integrations.deletion import asset_owner_deletion_guard
from app.integrations.observability.metrics_source.providers import provider_definition
from app.integrations.runtime.presentation import runtime_history_view, runtime_observation_state_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.storage.object_storage.providers.minio.capabilities import API_CAPABILITIES, CAPABILITY_PROFILE
from app.integrations.storage.object_storage.providers.minio.compatibility import compatibility_policy_view
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.minio import MinioInstance
from app.object_storage.providers.minio.service import (
    alert_source_for_binding,
    current_alert_binding,
    current_metrics_binding,
    metrics_source_for_binding,
)


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


def build_index_context(query: MinioIndexQuery | None = None) -> dict[str, Any]:
    query = query or MinioIndexQuery()
    instances = (
        MinioInstance.query.join(MinioInstance.integration_instance).order_by(IntegrationInstance.name.asc()).all()
    )
    registry_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    total_bindings = 0
    metrics_bound = 0
    alerts_bound = 0

    for instance in instances:
        metrics_binding = current_metrics_binding(instance)
        metrics_source = metrics_source_for_binding(metrics_binding)
        alert_binding = current_alert_binding(instance)
        alert_source = alert_source_for_binding(alert_binding)
        metrics_status = _source_binding_status(metrics_source, metrics_binding)
        metrics_source_label = _metrics_source_label(metrics_source)
        alert_status = _source_binding_status(alert_source, alert_binding)
        binding_count = int(metrics_binding is not None) + int(alert_binding is not None)
        total_bindings += binding_count
        metrics_bound += int(metrics_binding is not None)
        alerts_bound += int(alert_binding is not None)
        registry_rows.append(
            {
                'id': instance.id,
                'name': instance.name,
                'environment': instance.environment,
                'endpoint': instance.endpoint,
                'asset_name': instance.object_storage_system.name,
                'readiness_status': instance.readiness_status or 'validation_required',
                'compatibility_profile': instance.compatibility_profile,
                'declared_release': instance.declared_release,
                'metrics_status': metrics_status,
                'alert_status': alert_status,
                'binding_count': binding_count,
            }
        )
        uncovered = metrics_binding is None or alert_binding is None
        coverage_rows.append(
            {
                'asset_name': instance.object_storage_system.name,
                'environment': instance.environment,
                'instance': instance,
                'api_status': _provider_status(instance),
                'metrics_source': metrics_source,
                'metrics_source_label': metrics_source_label,
                'metrics_status': metrics_status,
                'alert_source': alert_source,
                'alert_status': alert_status,
                'coverage_status': 'attention' if uncovered or instance.readiness_status != 'ready' else 'ready',
                'coverage_label': 'Attention' if uncovered or instance.readiness_status != 'ready' else 'Ready',
            }
        )

    filtered_registry_rows = _filter_registry_rows(
        registry_rows,
        query=query.query,
        environment=query.environment,
        readiness=query.readiness,
        compatibility=query.compatibility,
    )
    filtered_coverage_rows = _filter_coverage_rows(
        coverage_rows,
        query=query.coverage_query,
        environment=query.coverage_environment,
        status=query.coverage_status,
    )
    registry_page_rows, pagination = _paginate(filtered_registry_rows, page=query.page, per_page=query.per_page)
    coverage_page_rows, coverage_pagination = _paginate(
        filtered_coverage_rows,
        page=query.coverage_page,
        per_page=query.coverage_per_page,
    )
    ready = sum(1 for item in instances if item.readiness_status == 'ready')
    return {
        'rows': registry_page_rows,
        'coverage_rows': coverage_page_rows,
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
        'registry_has_active_filters': bool(query.query or query.environment or query.readiness or query.compatibility),
        'coverage_has_active_filters': bool(
            query.coverage_query or query.coverage_environment or query.coverage_status
        ),
        'environment_options': sorted({row['environment'] for row in registry_rows if row.get('environment')}),
        'readiness_options': [
            {'value': 'ready', 'label': 'Ready'},
            {'value': 'blocked', 'label': 'Blocked'},
            {'value': 'validation_required', 'label': 'Validation Required'},
        ],
        'compatibility_options': sorted(
            {row['compatibility_profile'] for row in registry_rows if row.get('compatibility_profile')}
        ),
        'coverage_environment_options': sorted({row['environment'] for row in coverage_rows if row.get('environment')}),
        'coverage_status_options': [
            {'value': 'ready', 'label': 'Ready'},
            {'value': 'attention', 'label': 'Attention'},
        ],
        'stats': {
            'total': len(instances),
            'configured': len(instances),
            'ready': ready,
            'attention': len(instances) - ready,
            'bindings': total_bindings,
            'metrics_bound': metrics_bound,
            'alerts_bound': alerts_bound,
            'uncovered': sum(1 for row in coverage_rows if row['coverage_status'] != 'ready'),
        },
    }


def _metrics_source_label(source: object | None) -> str:
    if source is None:
        return 'No Metrics Source Binding'
    provider_key = str(getattr(source, 'provider_key', None) or '').strip().lower()
    return provider_definition(provider_key).label if provider_key else 'Metrics Source'


def _filter_registry_rows(
    rows: list[dict[str, Any]],
    *,
    query: str,
    environment: str,
    readiness: str,
    compatibility: str,
) -> list[dict[str, Any]]:
    normalized_query = str(query or '').strip().lower()
    filtered = rows
    if normalized_query:
        filtered = [
            row
            for row in filtered
            if normalized_query
            in ' '.join(
                str(value or '')
                for value in (
                    row.get('name'),
                    row.get('asset_name'),
                    row.get('environment'),
                    row.get('compatibility_profile'),
                    row.get('declared_release'),
                )
            ).lower()
        ]
    if environment:
        filtered = [row for row in filtered if row.get('environment') == environment]
    if readiness:
        filtered = [row for row in filtered if row.get('readiness_status') == readiness]
    if compatibility:
        filtered = [row for row in filtered if row.get('compatibility_profile') == compatibility]
    return filtered


def _filter_coverage_rows(
    rows: list[dict[str, Any]],
    *,
    query: str,
    environment: str,
    status: str,
) -> list[dict[str, Any]]:
    normalized_query = str(query or '').strip().lower()
    filtered = rows
    if normalized_query:
        filtered = [
            row
            for row in filtered
            if normalized_query
            in ' '.join(
                str(value or '')
                for value in (
                    row.get('asset_name'),
                    row.get('environment'),
                    getattr(row.get('instance'), 'name', ''),
                    getattr(row.get('metrics_source'), 'name', ''),
                    getattr(row.get('alert_source'), 'name', ''),
                )
            ).lower()
        ]
    if environment:
        filtered = [row for row in filtered if row.get('environment') == environment]
    if status:
        filtered = [row for row in filtered if row.get('coverage_status') == status]
    return filtered


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

    all_binding_rows = _asset_binding_rows(instance)
    binding_rows, binding_pagination = paginate_sequence(
        all_binding_rows,
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
        'binding_total': len(all_binding_rows),
        'binding_pagination': binding_pagination,
        'capability_registry': capability_registry,
        'compatibility_policy': compatibility_policy_view(
            instance.detected_product or 'minio', instance.declared_release
        ),
        'validated_at_display': present_user_datetime(instance.last_validated_at, empty='Not validated'),
        'checked_at_display': present_user_datetime(instance.last_checked_at, empty='Not observed'),
        'bucket_count': len(instance.object_storage_system.buckets or ()),
        'inventory_observed_at_display': present_user_datetime(
            instance.object_storage_system.inventory_observed_at,
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
        row_status = 'ready' if definition.key in observed else 'blocked'
        available = row_status == 'ready'
        rows.append(
            {
                'key': definition.key,
                'label': definition.label,
                'description': definition.description,
                'required': bool(definition.required),
                'requirement_label': 'Required' if definition.required else 'Optional',
                'status': row_status,
                'status_label': 'Ready' if available else 'Blocked',
                'available': available,
                'contract': CAPABILITY_PROFILE,
                'category': 'MinIO S3 API',
                'source_owner': 'MinIO S3 API',
                'evidence': (
                    f'Full Validation observed {definition.label} in the persisted MinIO capability snapshot.'
                    if available
                    else f'Full Validation did not observe {definition.label} in the current MinIO capability snapshot.'
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
                    else 'Verify the registered MinIO credential can perform this read-only operation, then rerun Full Validation.'
                ),
                'remediation': (
                    []
                    if available
                    else [
                        'Verify the registered MinIO endpoint and read-only credential permissions.',
                        'Rerun Full Validation and confirm this capability becomes Ready.',
                    ]
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
    if normalized_status in {'ready', 'blocked'}:
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


def _asset_binding_rows(instance: MinioInstance) -> list[dict[str, Any]]:
    return build_bound_observability_source_rows(
        asset_type='object_storage_system',
        asset_key=instance.object_storage_system_id,
    )


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
