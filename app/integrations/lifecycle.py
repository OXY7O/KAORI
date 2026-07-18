from __future__ import annotations

from typing import Any

from app.extensions.db import db
from app.models.integration import IntegrationBinding, IntegrationInstance


def ensure_canonical_instance(provider_record: Any, *, provider_type: str) -> IntegrationInstance:
    canonical_id = getattr(provider_record, 'integration_instance_id', None)
    canonical = db.session.get(IntegrationInstance, canonical_id) if canonical_id else None
    if canonical is None:
        canonical = IntegrationInstance(provider_type=provider_type, name=provider_record.name)
        db.session.add(canonical)
        db.session.flush()
        provider_record.integration_instance_id = canonical.id
    canonical.name = provider_record.name
    canonical.description = getattr(provider_record, 'description', None)
    canonical.enabled = bool(getattr(provider_record, 'enabled', True))
    canonical.readiness_status = getattr(provider_record, 'readiness_status', None)
    canonical.health_status = getattr(provider_record, 'last_status', None)
    canonical.last_error = getattr(provider_record, 'last_error', None)
    canonical.last_checked_at = getattr(provider_record, 'last_checked_at', None)
    canonical.metadata_json = {
        'provider_record_id': provider_record.id,
        'endpoint_product': getattr(provider_record, 'endpoint_product', None),
    }
    return canonical


def bind_instance(
    canonical: IntegrationInstance,
    *,
    asset_type: str,
    asset_key: str,
    role: str = 'primary',
    priority: int = 100,
    capability_scope: list[str] | None = None,
) -> IntegrationBinding:
    binding = IntegrationBinding.query.filter_by(
        integration_instance_id=canonical.id,
        asset_type=asset_type,
        asset_key=str(asset_key),
        binding_role=role,
    ).first()
    if binding is None:
        binding = IntegrationBinding(
            integration_instance_id=canonical.id,
            asset_type=asset_type,
            asset_key=str(asset_key),
            binding_role=role,
        )
        db.session.add(binding)
    binding.priority = priority
    binding.enabled = True
    binding.capability_scope = capability_scope
    return binding
