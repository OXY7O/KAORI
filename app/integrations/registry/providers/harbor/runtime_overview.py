"""Committed Harbor runtime evidence for the global Integrations Overview."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import selectinload

from app.common.presentation import present_user_datetime
from app.integrations.provider_matrix import provider_kind
from app.models.harbor import HarborInstance
from app.models.integration import IntegrationInstance


def build_runtime_overview_rows(
    latest: Mapping[tuple[str, str], Any],
    canonical_id: int | None = None,
) -> list[dict[str, Any]]:
    query = HarborInstance.query.join(HarborInstance.integration_instance).options(
        selectinload(HarborInstance.integration_instance).selectinload(IntegrationInstance.bindings)
    )
    if canonical_id is not None:
        query = query.filter(HarborInstance.integration_instance_id == int(canonical_id))
    instances = query.order_by(IntegrationInstance.name.asc()).all()
    return [_runtime_row(instance, latest.get(('registry', str(instance.id)))) for instance in instances]


def _runtime_row(instance: HarborInstance, observation: Any | None) -> dict[str, Any]:
    canonical = instance.integration_instance
    provider = provider_kind('registry', canonical.provider_key)
    enabled_bindings = [binding for binding in canonical.bindings if binding.enabled]
    capability_attention = 0 if instance.capabilities else 1
    latency_ms = observation.latency_ms if observation else None
    readiness = (
        (instance.readiness_status or 'validation_required')
        if canonical.enabled and canonical.lifecycle_status == 'active'
        else 'blocked'
    )
    return {
        'integration_type': 'registry',
        'provider_key': provider.key,
        'adapter_key': canonical.adapter_key,
        'provider_label': provider.label,
        'provider_icon': 'package',
        'instance_id': str(instance.id),
        'detail_key': f'registry:{canonical.id}',
        'instance_name': canonical.name,
        'scope_label': f'{len(enabled_bindings)} asset binding(s)',
        'endpoint_product': 'Harbor Registry',
        'connection_status': instance.last_status or 'not_observed',
        'health_status': observation.health_status if observation else 'not_observed',
        'health_score': observation.health_score if observation else None,
        'readiness': readiness,
        'observed_at': observation.observed_at if observation else None,
        'observed_at_display': present_user_datetime(
            observation.observed_at if observation else None, empty='Not observed'
        ),
        'validation_at_display': present_user_datetime(
            instance.last_checked_at or instance.last_validated_at, empty='Not validated'
        ),
        'latency_ms': latency_ms,
        'latency_display': f'{latency_ms} ms' if latency_ms is not None else None,
        'capability_profile': instance.capability_profile or instance.compatibility_profile,
        'capability_attention': capability_attention,
        'capability_attention_display': (
            'No Capability Attention' if not capability_attention else '1 Item Needs Attention'
        ),
        'message': (
            (observation.message if observation else None) or instance.validation_message or instance.last_error
        ),
        'binding_count': len(enabled_bindings),
    }
