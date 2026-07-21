from __future__ import annotations

from typing import Any

from app.extensions.db import db
from app.models.integration import IntegrationBinding, IntegrationInstance


def ensure_canonical_instance(provider_record: Any, *, provider_type: str) -> IntegrationInstance:
    """Create or update the canonical identity for a provider record.

    A new provider row can already be pending in the SQLAlchemy session while its
    ``integration_instance_id`` column is NOT NULL.  Flushing the whole session
    while creating the canonical identity would therefore try to insert the
    provider row too early.  Flush only the new IntegrationInstance first, assign
    its generated ID to the provider, and let the caller flush the complete unit
    of work afterwards.
    """
    canonical_id = getattr(provider_record, 'integration_instance_id', None)
    canonical = db.session.get(IntegrationInstance, canonical_id) if canonical_id else None

    if canonical is None:
        canonical = IntegrationInstance(
            provider_type=provider_type,
            name=provider_record.name,
        )
        db.session.add(canonical)

        # Critical: do not flush the complete session here. The provider record
        # may still have integration_instance_id=None and a NOT NULL constraint.
        db.session.flush([canonical])
        provider_record.integration_instance_id = canonical.id

    canonical.name = provider_record.name
    canonical.description = getattr(provider_record, 'description', None)
    canonical.enabled = bool(getattr(provider_record, 'enabled', True))
    canonical.readiness_status = getattr(provider_record, 'readiness_status', None)
    canonical.health_status = getattr(provider_record, 'last_status', None)
    canonical.last_error = getattr(provider_record, 'last_error', None)
    canonical.last_checked_at = getattr(provider_record, 'last_checked_at', None)
    canonical.metadata_json = {
        # This is intentionally None before the provider's first flush and is
        # refreshed by the second lifecycle call after the provider receives ID.
        'provider_record_id': getattr(provider_record, 'id', None),
        'endpoint_product': getattr(provider_record, 'endpoint_product', None),
    }
    return canonical


def invalidate_bindings(
    canonical: IntegrationInstance,
    *,
    message: str,
) -> int:
    """Invalidate provider bindings when the connection contract changes.

    Binding freshness is state-driven, not timestamp-driven. Runtime and full
    provider validation may update provider timestamps without changing the
    selector contract. Only an explicit connection or selector change should
    return a binding to ``validation_required``.
    """
    count = 0
    for binding in IntegrationBinding.query.filter_by(
        integration_instance_id=canonical.id,
        enabled=True,
    ).all():
        binding.validation_status = 'validation_required'
        binding.validation_message = message
        binding.last_validated_at = None
        count += 1
    return count


def bind_instance(
    canonical: IntegrationInstance,
    *,
    asset_type: str,
    asset_key: str,
    role: str = 'primary',
    priority: int = 100,
    capability_scope: list[str] | None = None,
    selector_json: dict | None = None,
    validation_status: str | None = None,
    validation_message: str | None = None,
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
    if selector_json is not None:
        binding.selector_json = selector_json
    if validation_status is not None:
        binding.validation_status = validation_status
    if validation_message is not None:
        binding.validation_message = validation_message
    return binding
