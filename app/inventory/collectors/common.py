from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any


def _isoformat_datetime(value: Any) -> str | None:
    if value is None:
        return None

    isoformat = getattr(value, 'isoformat', None)
    if callable(isoformat):
        return str(isoformat())

    return str(value)


def _string_value(value, default: str = '-') -> str:
    if value is None or value == '':
        return default

    return str(value)


def _model_value(source, *keys: str, default=None):
    """Read Kubernetes model attributes and raw/dict payloads consistently."""
    if source is None:
        return default

    for key in keys:
        if isinstance(source, dict):
            if key in source:
                return source[key]
        else:
            value = getattr(source, key, None)
            if value is not None:
                return value

    return default


def _to_modelish(value: Any) -> Any:
    """Convert raw discovery payloads to attribute objects used by collectors."""
    if isinstance(value, list):
        return [_to_modelish(item) for item in value]
    if not isinstance(value, dict):
        return value

    def snake(name: str) -> str:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    return SimpleNamespace(**{snake(key): _to_modelish(item) for key, item in value.items()})



def _mapping_dict(value: Any) -> dict[str, Any]:
    """Return Kubernetes mapping fields from model, dict, or raw discovery objects."""
    if isinstance(value, dict):
        return dict(value)
    attributes = getattr(value, '__dict__', None)
    if isinstance(attributes, dict):
        return dict(attributes)
    return {}


def _metadata_details(metadata) -> dict:
    labels = dict(sorted(_mapping_dict(_model_value(metadata, 'labels', default={})).items()))
    annotations = dict(sorted(_mapping_dict(_model_value(metadata, 'annotations', default={})).items()))

    return {
        'uid': _string_value(_model_value(metadata, 'uid')),
        'labels': labels,
        'annotations': annotations,
    }


def _toleration_display(toleration) -> str:
    key = _model_value(toleration, 'key') or '*'
    operator = _model_value(toleration, 'operator') or 'Equal'
    value = _model_value(toleration, 'value')
    effect = _model_value(toleration, 'effect')

    expression = key
    if operator == 'Exists':
        expression = f'{key} exists'
    elif value not in (None, ''):
        expression = f'{key}={value}'

    if effect:
        expression = f'{expression}:{effect}'

    return expression


def _detail_row(label: str, value) -> dict[str, str]:
    return {
        'label': label,
        'value': _string_value(value),
    }
