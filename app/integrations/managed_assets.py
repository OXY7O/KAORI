from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.integrations.provider_matrix import IntegrationProviderKind, provider_kind
from app.integrations.registry import get_integration
from app.models.integration import IntegrationInstance


@dataclass(frozen=True, slots=True)
class ManagedAssetOwner:
    """Canonical provider ownership for one managed operational asset."""

    identity: IntegrationInstance
    provider: IntegrationProviderKind
    record: Any

    @property
    def integration_type(self) -> str:
        return self.identity.integration_type

    @property
    def provider_key(self) -> str:
        return self.identity.provider_key

    @property
    def adapter_key(self) -> str:
        return self.identity.adapter_key


def managed_asset_owner_identity(
    *,
    asset_type: str,
    asset_key: str,
    integration_type: str | None = None,
) -> IntegrationInstance | None:
    """Resolve asset ownership without importing a product-specific model.

    Asset-owning integrations persist the managed asset identity in canonical
    ``IntegrationInstance.metadata_json``. Consumer bindings remain separate.
    """

    normalized_type = str(asset_type or '').strip()
    normalized_key = str(asset_key or '').strip()
    if not normalized_type or not normalized_key:
        return None
    query = IntegrationInstance.query.filter(
        IntegrationInstance.metadata_json['asset_type'].as_string() == normalized_type,
        IntegrationInstance.metadata_json['asset_key'].as_string() == normalized_key,
    )
    if integration_type:
        query = query.filter(IntegrationInstance.integration_type == str(integration_type).strip().lower())
    return query.order_by(IntegrationInstance.id.asc()).first()


def managed_asset_owner(
    *,
    asset_type: str,
    asset_key: str,
    integration_type: str | None = None,
) -> ManagedAssetOwner | None:
    identity = managed_asset_owner_identity(
        asset_type=asset_type,
        asset_key=asset_key,
        integration_type=integration_type,
    )
    if identity is None:
        return None
    module = get_integration(identity.integration_type)
    record = module.get_record_for_canonical(identity.id)
    if record is None:
        return None
    return ManagedAssetOwner(
        identity=identity,
        provider=provider_kind(identity.integration_type, identity.provider_key),
        record=record,
    )


def object_storage_owner(asset_key: str) -> ManagedAssetOwner | None:
    return managed_asset_owner(
        asset_type='object_storage_system',
        asset_key=asset_key,
        integration_type='object_storage',
    )
