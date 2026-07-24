from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from app.models import Cluster

_TYPE_KEY = '__kaori_materialized_type__'


def encode_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return {_TYPE_KEY: 'datetime', 'value': value.isoformat()}
    if isinstance(value, date):
        return {_TYPE_KEY: 'date', 'value': value.isoformat()}
    if isinstance(value, Decimal):
        return {_TYPE_KEY: 'decimal', 'value': str(value)}
    if isinstance(value, Enum):
        return encode_value(value.value)
    if isinstance(value, UUID):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return encode_value(asdict(value))
    if isinstance(value, Cluster):
        return {_TYPE_KEY: 'cluster', 'id': value.id}
    if isinstance(value, dict):
        return {str(key): encode_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [encode_value(item) for item in value]
    raise TypeError(f'Unsupported analytics snapshot value: {type(value).__name__}')


def decode_value(value: Any) -> Any:
    if isinstance(value, list):
        return [decode_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    value_type = value.get(_TYPE_KEY)
    if value_type == 'datetime':
        return datetime.fromisoformat(str(value['value']))
    if value_type == 'date':
        return date.fromisoformat(str(value['value']))
    if value_type == 'decimal':
        return Decimal(str(value['value']))
    if value_type == 'cluster':
        return Cluster.query.get(int(value['id']))
    return {key: decode_value(item) for key, item in value.items()}
