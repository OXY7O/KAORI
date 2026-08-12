from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.object_storage import ObjectStorageSystem


@dataclass(frozen=True, slots=True)
class ConsumerAssetDefinition:
    """One managed-asset family eligible for reusable observability sources."""

    asset_type: str
    label: str
    plural_label: str
    icon: str
    selector_label: str
    selector_placeholder: str
    model: type[Any]


@dataclass(frozen=True, slots=True)
class ConsumerAssetChoice:
    key: str
    name: str
    environment: str


@dataclass(frozen=True, slots=True)
class ConsumerAssetGroup:
    asset_type: str
    label: str
    plural_label: str
    icon: str
    selector_label: str
    selector_placeholder: str
    profile_key: str
    profile_label: str
    assets: tuple[ConsumerAssetChoice, ...]


_DEFINITIONS: tuple[ConsumerAssetDefinition, ...] = (
    ConsumerAssetDefinition(
        asset_type='kubernetes_cluster',
        label='Kubernetes Cluster',
        plural_label='Kubernetes Clusters',
        icon='boxes',
        selector_label='cluster',
        selector_placeholder='k8s-production',
        model=Cluster,
    ),
    ConsumerAssetDefinition(
        asset_type='object_storage_system',
        label='Object Storage System',
        plural_label='Object Storage Systems',
        icon='database',
        selector_label='job',
        selector_placeholder='minio-production',
        model=ObjectStorageSystem,
    ),
)
_DEFINITIONS_BY_TYPE = {definition.asset_type: definition for definition in _DEFINITIONS}


def registered_consumer_asset_definitions() -> tuple[ConsumerAssetDefinition, ...]:
    return _DEFINITIONS


def get_consumer_asset_definition(asset_type: str) -> ConsumerAssetDefinition | None:
    return _DEFINITIONS_BY_TYPE.get(str(asset_type or '').strip())


def resolve_consumer_asset(asset_type: str, asset_key: str) -> Any | None:
    definition = get_consumer_asset_definition(asset_type)
    key = str(asset_key or '').strip()
    if definition is None or not key:
        return None
    return db.session.get(definition.model, key)


def consumer_asset_name(asset_type: str, asset_key: str) -> str:
    asset = resolve_consumer_asset(asset_type, asset_key)
    if asset is not None:
        return str(getattr(asset, 'name', '') or asset_key)
    definition = get_consumer_asset_definition(asset_type)
    return definition.label if definition is not None else 'Consumer Asset'


def build_consumer_asset_groups(
    profile_resolver: Callable[[str], Any | None],
) -> tuple[ConsumerAssetGroup, ...]:
    """Build the source-owned binding picker from the canonical asset registry.

    A new managed asset (for example Vault) becomes bindable by registering its
    asset definition here and a provider-specific consumer profile. Source pages
    do not need a new product-specific binding form.
    """

    groups: list[ConsumerAssetGroup] = []
    for definition in _DEFINITIONS:
        profile = profile_resolver(definition.asset_type)
        if profile is None:
            continue
        assets = tuple(
            ConsumerAssetChoice(
                key=str(asset.id),
                name=str(asset.name),
                environment=str(getattr(asset, 'environment', '') or ''),
            )
            for asset in definition.model.query.order_by(definition.model.name.asc()).all()
        )
        groups.append(
            ConsumerAssetGroup(
                asset_type=definition.asset_type,
                label=definition.label,
                plural_label=definition.plural_label,
                icon=definition.icon,
                selector_label=definition.selector_label,
                selector_placeholder=definition.selector_placeholder,
                profile_key=str(profile.profile_key),
                profile_label=str(profile.label),
                assets=assets,
            )
        )
    return tuple(groups)
