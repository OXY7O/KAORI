from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.definitions.loader import DefinitionError


def require_mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DefinitionError(f'{path} must be a mapping.')
    return value


def require_list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise DefinitionError(f'{path} must be a list.')
    return value


def require_str(mapping: Mapping[str, Any], key: str, path: str, *, allow_empty: bool = False) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise DefinitionError(f'{path}.{key} must be a string.')
    normalized = value.strip()
    if not normalized and not allow_empty:
        raise DefinitionError(f'{path}.{key} must not be empty.')
    return normalized


def optional_str(mapping: Mapping[str, Any], key: str, path: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DefinitionError(f'{path}.{key} must be a string or null.')
    return value.strip() or None


def require_bool(mapping: Mapping[str, Any], key: str, path: str, *, default: bool | None = None) -> bool:
    value = mapping.get(key, default)
    if not isinstance(value, bool):
        raise DefinitionError(f'{path}.{key} must be a boolean.')
    return value


def require_int(mapping: Mapping[str, Any], key: str, path: str, *, default: int | None = None) -> int:
    value = mapping.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise DefinitionError(f'{path}.{key} must be an integer.')
    return value


def string_tuple(value: object, path: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DefinitionError(f'{path} must be a list of strings.')
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise DefinitionError(f'{path}[{index}] must be a non-empty string.')
        result.append(item.strip())
    return tuple(result)


def unique_by(items: Sequence[Mapping[str, Any]], key: str, path: str) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items):
        value = require_str(item, key, f'{path}[{index}]')
        if value in seen:
            raise DefinitionError(f'Duplicate {path}.{key}: {value!r}.')
        seen.add(value)


def allowed(value: str, choices: set[str] | frozenset[str], path: str) -> str:
    if value not in choices:
        raise DefinitionError(f'{path} has unsupported value {value!r}; expected one of {sorted(choices)}.')
    return value
