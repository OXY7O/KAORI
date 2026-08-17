from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.common.presentation import present_key_label
from app.extensions.db import db
from app.integrations.provider_matrix import provider_kind
from app.models.integration import IntegrationBinding, IntegrationInstance


@dataclass(frozen=True, slots=True)
class BindingPersistenceSpec:
    asset_type: str
    asset_key: str
    role: str = 'primary'
    priority: int = 100
    capability_scope: list[str] | None = None
    selector_json: dict | None = None
    routing_policy: dict | None = None
    validation_status: str | None = None
    validation_profile: str | None = None
    validation_evidence: dict | None = None
    validation_message: str | None = None


def ensure_provider_operational(provider_record: Any, *, integration_type: str) -> IntegrationInstance:
    """Return the active canonical identity or fail before provider I/O.

    Workers and synchronous operations must reload their provider record and call
    this guard immediately before touching an external endpoint.  Administrative
    lifecycle state is authoritative even when a task was queued while active.
    """
    provider_enabled = getattr(provider_record, 'enabled', None)
    if provider_enabled is not None and not bool(provider_enabled):
        raise RuntimeError(
            f'{present_key_label(integration_type)} operation was canceled because the provider instance is disabled.'
        )
    canonical = getattr(provider_record, 'integration_instance', None)
    if canonical is None:
        raise RuntimeError(
            f'{present_key_label(integration_type)} operation was canceled because canonical integration identity is missing.'
        )
    lifecycle_status = str(getattr(canonical, 'lifecycle_status', '') or '').strip().lower()
    if not bool(getattr(canonical, 'enabled', False)) or lifecycle_status != 'active':
        raise RuntimeError(
            f'{present_key_label(integration_type)} operation was canceled because the integration is no longer active.'
        )
    return canonical


def ensure_canonical_instance(provider_record: Any, *, integration_type: str) -> IntegrationInstance:
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
        canonical = IntegrationInstance()
        canonical.integration_type = integration_type
        canonical.name = name
        canonical.enabled = True
        canonical.readiness_status = 'validation_required'
        provider_record.integration_instance = canonical
        db.session.add(canonical)

    if canonical.integration_type != integration_type:
        raise ValueError(
            f'Integration identity mismatch: expected {integration_type}, found {canonical.integration_type}.'
        )

    metadata = dict(canonical.metadata_json or {})
    metadata.update(
        {
            'provider_record_id': getattr(provider_record, 'id', None),
            'endpoint_product': getattr(provider_record, 'endpoint_product', None),
        }
    )
    provider_key = str(getattr(provider_record, 'provider_key', None) or canonical.provider_key or '').strip().lower()
    adapter_key = str(getattr(provider_record, 'adapter_key', None) or canonical.adapter_key or '').strip().lower()
    if provider_key and adapter_key:
        definition = provider_kind(integration_type, provider_key)
        if definition.adapter_key != adapter_key:
            raise ValueError(
                f'Provider adapter mismatch for {integration_type}/{provider_key}: '
                f'expected {definition.adapter_key}, found {adapter_key}.'
            )
        if not definition.available:
            raise ValueError(f'Provider {definition.label} is planned and cannot be activated yet.')
        canonical.provider_key = provider_key
        canonical.adapter_key = adapter_key
    if integration_type == 'metrics_source':
        metadata['metrics_query_language'] = getattr(provider_record, 'query_language', None)
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
        binding.validation_evidence = None
        binding.validation_message = message
        binding.last_validated_at = None
        count += 1
    return count


def bind_instance(
    canonical: IntegrationInstance,
    *,
    spec: BindingPersistenceSpec,
) -> IntegrationBinding:
    binding = IntegrationBinding.query.filter_by(
        integration_instance_id=canonical.id,
        asset_type=spec.asset_type,
        asset_key=str(spec.asset_key),
        binding_role=spec.role,
    ).first()
    if binding is None:
        binding = IntegrationBinding()
        binding.integration_instance_id = canonical.id
        binding.asset_type = spec.asset_type
        binding.asset_key = str(spec.asset_key)
        binding.binding_role = spec.role
        db.session.add(binding)
    binding.priority = spec.priority
    binding.enabled = True
    binding.capability_scope = spec.capability_scope
    if spec.selector_json is not None:
        binding.selector_json = spec.selector_json
    if spec.routing_policy is not None:
        binding.routing_policy = spec.routing_policy
    if spec.validation_status is not None:
        binding.validation_status = spec.validation_status
    if spec.validation_profile is not None:
        binding.validation_profile = spec.validation_profile
    if spec.validation_evidence is not None:
        binding.validation_evidence = spec.validation_evidence
    if spec.validation_message is not None:
        binding.validation_message = spec.validation_message
    return binding
