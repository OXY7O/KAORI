from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.common.presentation import present_user_datetime
from app.integrations.alertmanager.binding_profiles import get_alert_consumer_profile
from app.integrations.prometheus.binding_profiles import get_binding_validation_profile
from app.integrations.registry import get_integration
from app.integrations.runtime.presentation import runtime_observation_state_view
from app.integrations.runtime.repository import list_runtime_history
from app.minio.service import (
    alert_source_for_binding,
    current_alert_binding,
    current_metrics_binding,
    metrics_source_for_binding,
)
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.minio import MinioInstance


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
        alert_status = _source_binding_status(alert_source, alert_binding)
        own_binding_count = len(
            [
                binding
                for binding in instance.integration_instance.bindings
                if binding.asset_type == 'object_storage_system'
                and binding.asset_key == instance.object_storage_system_id
            ]
        )
        binding_count = own_binding_count + int(metrics_binding is not None) + int(alert_binding is not None)
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


def build_detail_context(instance: MinioInstance) -> dict[str, Any]:
    metrics_binding = current_metrics_binding(instance)
    metrics_source = metrics_source_for_binding(metrics_binding)
    alert_binding = current_alert_binding(instance)
    alert_source = alert_source_for_binding(alert_binding)
    runtime_history = list_runtime_history('minio', str(instance.id), limit=5)
    latest_runtime = runtime_history[0] if runtime_history else None
    runtime_state = runtime_observation_state_view(
        latest_runtime,
        fallback_readiness=instance.readiness_status or 'validation_required',
        fallback_compatibility_profile=instance.compatibility_profile,
        fallback_capabilities=tuple(instance.capabilities or ()),
    )
    own_binding = next(
        (
            item
            for item in instance.integration_instance.bindings
            if item.asset_type == 'object_storage_system'
            and item.asset_key == instance.object_storage_system_id
            and item.integration_instance_id == instance.integration_instance_id
        ),
        None,
    )
    binding_rows = _asset_binding_rows(instance)
    return {
        'instance': instance,
        'asset': instance.object_storage_system,
        'canonical': instance.integration_instance,
        'runtime_state': runtime_state,
        'runtime_history': [
            {
                'observed_at_display': present_user_datetime(row.observed_at, empty='Unknown', include_seconds=True),
                'readiness': row.readiness or 'validation_required',
                'health_status': row.health_status or 'not_observed',
                'health_score': row.health_score,
                'latency_ms': row.latency_ms,
                'message': row.message or '',
            }
            for row in runtime_history
        ],
        'api_binding': own_binding,
        'metrics_binding': metrics_binding,
        'metrics_source': metrics_source,
        'metrics_status': _source_binding_status(metrics_source, metrics_binding),
        'alert_binding': alert_binding,
        'alert_source': alert_source,
        'alert_status': _source_binding_status(alert_source, alert_binding),
        'binding_rows': binding_rows,
        'validated_at_display': present_user_datetime(instance.last_validated_at, empty='Not validated'),
        'checked_at_display': present_user_datetime(instance.last_checked_at, empty='Not observed'),
        'bucket_count': int((instance.validation_summary or {}).get('bucket_count') or 0),
        'capability_count': len(instance.capabilities or ()),
    }


def _asset_binding_rows(instance: MinioInstance) -> list[dict[str, Any]]:
    rows = (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationBinding.asset_type == 'object_storage_system',
            IntegrationBinding.asset_key == instance.object_storage_system_id,
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(
            IntegrationInstance.provider_type.asc(), IntegrationBinding.priority.asc(), IntegrationBinding.id.asc()
        )
        .all()
    )
    result: list[dict[str, Any]] = []
    for binding in rows:
        canonical = binding.instance
        module = get_integration(canonical.provider_type)
        source = module.get_record_for_canonical(canonical.id)
        if canonical.provider_type == 'prometheus':
            profile = get_binding_validation_profile(binding.asset_type)
            profile_label = profile.label if profile is not None else binding.validation_profile
        elif canonical.provider_type == 'alertmanager':
            profile = get_alert_consumer_profile(binding.asset_type)
            profile_label = profile.label if profile is not None else binding.validation_profile
        else:
            profile_label = 'Native Provider Contract'
        result.append(
            {
                'binding': binding,
                'provider_type': canonical.provider_type,
                'provider_label': module.label,
                'source_name': getattr(source, 'name', None) or canonical.name,
                'profile_label': profile_label or 'Validation Required',
                'validation_status': binding.validation_status or 'validation_required',
                'validation_message': binding.validation_message or 'Validation has not been recorded.',
            }
        )
    return result


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
