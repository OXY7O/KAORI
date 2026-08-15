from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.definitions.integration_registry import integration_taxonomy_document
from app.definitions.validation import require_list, require_mapping, require_str
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


_MODEL_BY_KEY: dict[str, type[Any]] = {
    'cluster': Cluster,
    'object_storage_system': ObjectStorageSystem,
}


def _load_definitions() -> tuple[ConsumerAssetDefinition, ...]:
    document = integration_taxonomy_document()
    definitions: list[ConsumerAssetDefinition] = []
    for index, raw in enumerate(require_list(document.get('consumer_assets'), 'consumer_assets')):
        item = require_mapping(raw, f'consumer_assets[{index}]')
        model_key = require_str(item, 'model_key', f'consumer_assets[{index}]')
        try:
            model = _MODEL_BY_KEY[model_key]
        except KeyError as exc:
            raise ValueError(f'Unknown consumer asset model_key: {model_key!r}.') from exc
        definitions.append(
            ConsumerAssetDefinition(
                asset_type=require_str(item, 'asset_type', f'consumer_assets[{index}]'),
                label=require_str(item, 'label', f'consumer_assets[{index}]'),
                plural_label=require_str(item, 'plural_label', f'consumer_assets[{index}]'),
                icon=require_str(item, 'icon', f'consumer_assets[{index}]'),
                selector_label=require_str(item, 'selector_label', f'consumer_assets[{index}]'),
                selector_placeholder=require_str(item, 'selector_placeholder', f'consumer_assets[{index}]'),
                model=model,
            )
        )
    return tuple(definitions)


_DEFINITIONS = _load_definitions()
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

    A new managed asset (for example Vault) becomes bindable by adding its
    source-controlled taxonomy definition plus a model adapter and compatible
    consumer profiles. Source pages do not need a new product-specific binding form.
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
