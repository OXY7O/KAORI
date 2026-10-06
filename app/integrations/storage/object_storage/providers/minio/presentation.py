from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import selectinload

from app.common.presentation import present_user_datetime
from app.integrations.provider_matrix import provider_kind
from app.models.integration import IntegrationInstance
from app.models.minio import MinioInstance


def build_runtime_overview_rows(
    latest: Mapping[tuple[str, str], Any],
    instance_id: int | None = None,
) -> list[dict[str, Any]]:
    query = MinioInstance.query.join(MinioInstance.integration_instance).options(
        selectinload(MinioInstance.integration_instance).selectinload(IntegrationInstance.bindings)
    )
    if instance_id is not None:
        query = query.filter(MinioInstance.id == int(instance_id))
    instances = query.order_by(IntegrationInstance.name.asc()).all()
    return [_runtime_row(instance, latest.get(('object_storage', str(instance.id)))) for instance in instances]


def _runtime_row(instance: MinioInstance, observation: Any | None) -> dict[str, Any]:
    validation_at = instance.last_checked_at or instance.last_validated_at
    capability_attention = 0 if instance.capabilities else 1
    enabled_bindings = [binding for binding in instance.integration_instance.bindings if binding.enabled]
    latency_ms = observation.latency_ms if observation else None
    canonical = instance.integration_instance
    provider = provider_kind('object_storage', canonical.provider_key)
    return {
        'integration_type': 'object_storage',
        'provider_key': provider.key,
        'adapter_key': canonical.adapter_key,
        'provider_label': provider.label,
        'provider_icon': 'database',
        'instance_id': str(instance.id),
        'detail_key': f'object_storage:{instance.id}',
        'instance_name': instance.name,
        'scope_label': instance.object_storage_system.name,
        'endpoint_product': (instance.detected_product or 'minio').replace('_', ' ').title(),
        'connection_status': instance.last_status or 'not_observed',
        'health_status': observation.health_status if observation else 'not_observed',
        'health_score': observation.health_score if observation else None,
        'readiness': instance.readiness_status or 'validation_required',
        'observed_at': observation.observed_at if observation else None,
        'observed_at_display': present_user_datetime(
            observation.observed_at if observation else None,
            empty='Not observed',
        ),
        'validation_at_display': present_user_datetime(validation_at, empty='Not validated'),
        'latency_ms': latency_ms,
        'latency_display': f'{latency_ms} ms' if latency_ms is not None else None,
        'capability_profile': instance.capability_profile,
        'capability_attention': capability_attention,
        'capability_attention_display': _capability_attention_display(capability_attention),
        'message': (observation.message if observation else None) or instance.validation_message or instance.last_error,
        'binding_count': len(enabled_bindings),
    }


def _capability_attention_display(count: int) -> str:
    if count <= 0:
        return 'No Capability Attention'
    if count == 1:
        return '1 Item Needs Attention'
    return f'{count} Items Need Attention'
