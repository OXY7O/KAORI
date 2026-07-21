from __future__ import annotations

from typing import Any

from app.extensions.db import db
from app.models.integration import IntegrationBinding, IntegrationInstance


def ensure_canonical_instance(provider_record: Any, *, provider_type: str) -> IntegrationInstance:
    """Return the canonical identity owned by a provider-specific record.

    Shared identity and runtime fields live only on IntegrationInstance. Provider
    records expose those values through SQLAlchemy association proxies and retain
    only connection-specific configuration and evidence.
    """
    canonical = getattr(provider_record, 'integration_instance', None)
    if canonical is None:
        name = str(getattr(provider_record, 'name', '') or '').strip()
        if not name:
            raise ValueError('Provider identity requires a name before persistence.')
        canonical = IntegrationInstance(
            provider_type=provider_type,
            name=name,
            enabled=True,
            readiness_status='validation_required',
        )
        provider_record.integration_instance = canonical
        db.session.add(canonical)

    if canonical.provider_type != provider_type:
        raise ValueError(
            f'Provider identity mismatch: expected {provider_type}, found {canonical.provider_type}.'
        )

    metadata = dict(canonical.metadata_json or {})
    metadata.update({
        'provider_record_id': getattr(provider_record, 'id', None),
        'endpoint_product': getattr(provider_record, 'endpoint_product', None),
    })
    canonical.metadata_json = metadata
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
