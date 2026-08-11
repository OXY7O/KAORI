from __future__ import annotations

from typing import Any

from app.common.presentation import present_user_datetime
from app.integrations.runtime.presentation import runtime_observation_state_view
from app.integrations.runtime.repository import list_runtime_history
from app.minio.service import current_metrics_binding, metrics_source_for_binding
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.minio import MinioInstance


def build_index_context() -> dict[str, Any]:
    instances = (
        MinioInstance.query.join(MinioInstance.integration_instance).order_by(IntegrationInstance.name.asc()).all()
    )
    rows: list[dict[str, Any]] = []
    for instance in instances:
        binding = current_metrics_binding(instance)
        source = metrics_source_for_binding(binding)
        rows.append(
            {
                'id': instance.id,
                'name': instance.name,
                'environment': instance.environment,
                'asset_name': instance.object_storage_system.name,
                'readiness_status': instance.readiness_status or 'validation_required',
                'compatibility_profile': instance.compatibility_profile,
                'declared_release': instance.declared_release,
                'metrics_status': _metrics_status(source, binding),
            }
        )
    return {
        'rows': rows,
        'stats': {
            'total': len(instances),
            'ready': sum(1 for item in instances if item.readiness_status == 'ready'),
            'attention': sum(1 for item in instances if item.readiness_status != 'ready'),
            'metrics_bound': sum(1 for item in instances if current_metrics_binding(item) is not None),
        },
    }


def build_detail_context(instance: MinioInstance) -> dict[str, Any]:
    binding = current_metrics_binding(instance)
    metrics_source = metrics_source_for_binding(binding)
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
    return {
        'instance': instance,
        'asset': instance.object_storage_system,
        'canonical': instance.integration_instance,
        'runtime_state': runtime_state,
        'runtime_history': runtime_history,
        'api_binding': own_binding,
        'metrics_binding': binding,
        'metrics_source': metrics_source,
        'metrics_status': _metrics_status(metrics_source, binding),
        'validated_at_display': present_user_datetime(instance.last_validated_at, empty='Not validated'),
        'checked_at_display': present_user_datetime(instance.last_checked_at, empty='Not observed'),
        'bucket_count': int((instance.validation_summary or {}).get('bucket_count') or 0),
    }


def _metrics_status(source: Any | None, binding: IntegrationBinding | None) -> dict[str, str]:
    if source is None or binding is None:
        return {'status': 'not_configured', 'label': 'Not Bound'}
    if source.readiness_status == 'ready' and binding.validation_status == 'ready':
        return {'status': 'ready', 'label': 'Ready'}
    if binding.validation_status == 'blocked' or source.readiness_status == 'blocked':
        return {'status': 'blocked', 'label': 'Blocked'}
    return {'status': 'degraded', 'label': 'Validation Required'}
