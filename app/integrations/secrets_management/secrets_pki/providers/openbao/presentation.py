"""Committed OpenBao runtime overview; no provider requests or secret loading."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import defer, selectinload

from app.common.presentation import present_user_datetime
from app.integrations.secrets_management.secrets_pki.providers.openbao.service import local_provider_enabled
from app.models.integration import IntegrationInstance
from app.models.openbao import OpenBaoInstance


def build_runtime_overview_rows(
    latest: Mapping[tuple[str, str], Any], canonical_id: int | None = None
) -> list[dict[str, Any]]:
    query = OpenBaoInstance.query.join(OpenBaoInstance.integration_instance).options(
        defer(OpenBaoInstance.secret_id),
        selectinload(OpenBaoInstance.integration_instance).selectinload(IntegrationInstance.bindings),
    ).filter(
        IntegrationInstance.integration_type == 'secrets_pki',
        IntegrationInstance.provider_key == 'openbao',
        IntegrationInstance.adapter_key == 'openbao_http_v1',
    )
    if canonical_id is not None:
        query = query.filter(OpenBaoInstance.integration_instance_id == canonical_id)
    return [_runtime_row(row, latest.get(('secrets_pki', f'openbao:{row.id}'))) for row in query.all()]


def _runtime_row(row: OpenBaoInstance, observation: Any | None) -> dict[str, Any]:
    identity = row.integration_instance
    if observation is not None and (
        observation.integration_instance_id != identity.id or observation.provider_key != 'openbao'
        or observation.adapter_key != 'openbao_http_v1'
    ):
        observation = None
    active = local_provider_enabled() and identity.enabled and identity.lifecycle_status == 'active'
    return {
        'integration_type': 'secrets_pki',
        'provider_key': 'openbao',
        'adapter_key': 'openbao_http_v1',
        'provider_label': 'OpenBao',
        'provider_icon': 'key-round',
        'instance_id': f'openbao:{row.id}',
        'detail_key': f'secrets_pki:{identity.id}',
        'instance_name': row.name,
        'scope_label': row.ownership.title(),
        'endpoint_product': 'OpenBao',
        'connection_status': identity.health_status or 'not_observed',
        'health_status': observation.health_status if observation else 'not_observed',
        'health_score': observation.health_score if observation else None,
        'readiness': (identity.readiness_status or 'validation_required') if active else 'blocked',
        'observed_at': observation.observed_at if observation else None,
        'observed_at_display': present_user_datetime(observation.observed_at if observation else None, empty='Not observed'),
        'validation_at_display': present_user_datetime(row.last_validated_at, empty='Not validated'),
        'latency_ms': None,
        'latency_display': None,
        'capability_profile': 'openbao.local-connection.v1',
        'capability_attention': 1,
        'capability_attention_display': 'Credential Authority Needs Attention',
        'message': identity.last_error or 'Independent credential authority remains pending.',
        'binding_count': sum(binding.enabled for binding in identity.bindings),
    }
