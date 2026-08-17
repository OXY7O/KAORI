from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.extensions.db import db
from app.integrations.registry import get_integration
from app.integrations.repository import get_integration_record


@dataclass(frozen=True, slots=True)
class SourceBindingSpec:
    asset_type: str
    asset_key: str
    role: str = 'primary'
    priority: int = 100
    selector_label: str | None = None
    selector_value: str | None = None
    selector_operator: str = '='
    capability_scope: tuple[str, ...] | list[str] | None = None
    routing_policy: dict[str, Any] | None = None
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class CreatedSourceBinding:
    source: Any
    asset: Any | None
    binding: Any


def create_source_binding(
    integration_type: str,
    *,
    integration_instance_id: int,
    spec: SourceBindingSpec,
    asset: Any | None = None,
) -> CreatedSourceBinding:
    """Create one provider-to-asset binding through the registered provider adapter.

    The canonical binding remains asset-centric. Domain helpers may load a richer
    asset object for their UI, but the persisted contract is always asset_type +
    asset_key so new consumers such as object storage do not need a second binding
    table or a provider-to-provider foreign key.
    """
    type_key = str(integration_type or '').strip().lower()
    normalized_asset_type = str(spec.asset_type or '').strip()
    normalized_asset_key = str(spec.asset_key or '').strip()
    if not normalized_asset_type:
        raise ValueError('Select an operational asset type before saving the binding.')
    if not normalized_asset_key:
        raise ValueError('Select or enter an operational asset before saving the binding.')

    source = get_integration_record(type_key, integration_instance_id)
    if source is None:
        module = get_integration(type_key)
        raise ValueError(f'The selected {module.label} source no longer exists.')

    module = get_integration(type_key)
    if 'binding.create' not in module.operations:
        raise ValueError(f'{module.label} does not support source bindings.')

    try:
        binding = module.execute(
            'binding.create',
            source,
            scope_type=normalized_asset_type,
            scope_key=normalized_asset_key,
            role=spec.role,
            priority=spec.priority,
            enabled=spec.enabled,
            selector_label=spec.selector_label,
            selector_value=spec.selector_value,
            selector_operator=spec.selector_operator,
            capability_scope=spec.capability_scope,
            routing_policy=spec.routing_policy,
        )
    except Exception:
        db.session.rollback()
        raise

    return CreatedSourceBinding(source=source, asset=asset, binding=binding)
