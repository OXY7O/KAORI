from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class DefinitionError(ValueError):
    """Raised when a source-controlled KAORI definition is invalid."""


class _StrictSafeLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DefinitionError(f'Duplicate YAML key is not allowed: {key!r}.')
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


_DEFINITIONS_ROOT = Path(__file__).resolve().parent / 'catalogs'


def definition_path(relative_path: str) -> Path:
    path = (_DEFINITIONS_ROOT / relative_path).resolve()
    if _DEFINITIONS_ROOT.resolve() not in path.parents:
        raise DefinitionError(f'Definition path escapes registry root: {relative_path!r}.')
    return path


@lru_cache(maxsize=64)
def load_definition_document(relative_path: str, *, expected_kind: str) -> dict[str, Any]:
    path = definition_path(relative_path)
    if not path.is_file():
        raise DefinitionError(f'Definition file does not exist: {relative_path}.')
    try:
        document = yaml.load(path.read_text(encoding='utf-8'), Loader=_StrictSafeLoader)
    except yaml.YAMLError as exc:
        raise DefinitionError(f'Invalid YAML in {relative_path}: {exc}.') from exc
    if not isinstance(document, dict):
        raise DefinitionError(f'Definition root must be a mapping: {relative_path}.')
    schema_version = document.get('schema_version')
    if schema_version != 1:
        raise DefinitionError(
            f'Unsupported schema_version for {relative_path}: {schema_version!r}; expected 1.'
        )
    kind = str(document.get('kind') or '').strip()
    if kind != expected_kind:
        raise DefinitionError(
            f'Unexpected definition kind for {relative_path}: {kind!r}; expected {expected_kind!r}.'
        )
    return document


def clear_definition_cache() -> None:
    load_definition_document.cache_clear()
