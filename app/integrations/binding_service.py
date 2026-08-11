from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.extensions.db import db
from app.integrations.registry import get_integration
from app.integrations.repository import get_cluster, get_provider_record


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
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class CreatedSourceBinding:
    source: Any
    asset: Any | None
    binding: Any

    @property
    def cluster(self) -> Any | None:
        """Compatibility alias retained for the Kubernetes binding workspace."""
        return self.asset


def create_source_binding(
    provider_type: str,
    *,
    source_id: int,
    spec: SourceBindingSpec,
    asset: Any | None = None,
) -> CreatedSourceBinding:
    """Create one provider-to-asset binding through the registered provider adapter.

    The canonical binding remains asset-centric. Domain helpers may load a richer
    asset object for their UI, but the persisted contract is always asset_type +
    asset_key so new consumers such as object storage do not need a second binding
    table or a provider-to-provider foreign key.
    """
    provider = str(provider_type or '').strip().lower()
    normalized_asset_type = str(spec.asset_type or '').strip()
    normalized_asset_key = str(spec.asset_key or '').strip()
    if not normalized_asset_type:
        raise ValueError('Select an operational asset type before saving the binding.')
    if not normalized_asset_key:
        raise ValueError('Select or enter an operational asset before saving the binding.')

    source = get_provider_record(provider, source_id)
    if source is None:
        module = get_integration(provider)
        raise ValueError(f'The selected {module.label} source no longer exists.')

    module = get_integration(provider)
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
        )
    except Exception:
        db.session.rollback()
        raise

    return CreatedSourceBinding(source=source, asset=asset, binding=binding)


def create_cluster_source_binding(
    provider_type: str,
    *,
    source_id: int,
    cluster_id: str,
    role: str,
    priority: int,
    selector_label: str,
    selector_value: str,
    selector_operator: str,
) -> CreatedSourceBinding:
    """Compatibility wrapper for existing Kubernetes source-binding workflows."""
    cluster = get_cluster(cluster_id)
    if cluster is None:
        raise ValueError('The selected Kubernetes scope no longer exists.')

    return create_source_binding(
        provider_type,
        source_id=source_id,
        spec=SourceBindingSpec(
            asset_type='kubernetes_cluster',
            asset_key=str(cluster.id),
            role=role,
            priority=priority,
            selector_label=selector_label,
            selector_value=selector_value,
            selector_operator=selector_operator,
        ),
        asset=cluster,
    )
