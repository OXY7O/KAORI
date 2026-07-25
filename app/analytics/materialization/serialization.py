from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from app.models import Cluster

_TYPE_KEY = '__kaori_materialized_type__'


@dataclass(frozen=True, slots=True)
class ClusterReference:
    """Snapshot-safe cluster identity used by read-only analytics contexts.

    Analytics snapshots must never deserialize SQLAlchemy ORM entities into the
    presentation context. A background dispatch may commit or tear down the
    scoped session before Jinja renders the page, which would leave ORM objects
    detached and cause ``DetachedInstanceError``.
    """

    id: str
    name: str
    environment: str
    status: str = 'unknown'


def cluster_reference_from_model(cluster: Cluster) -> ClusterReference:
    return ClusterReference(
        id=str(cluster.id),
        name=str(cluster.name),
        environment=str(cluster.environment),
        status=str(cluster.status or 'unknown'),
    )


def load_cluster_reference(cluster_id: str) -> ClusterReference | None:
    row = (
        Cluster.query.with_entities(
            Cluster.id,
            Cluster.name,
            Cluster.environment,
            Cluster.status,
        )
        .filter(Cluster.id == str(cluster_id))
        .first()
    )
    if row is None:
        return None
    return ClusterReference(
        id=str(row.id),
        name=str(row.name),
        environment=str(row.environment),
        status=str(row.status or 'unknown'),
    )


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
    if isinstance(value, ClusterReference):
        return {
            _TYPE_KEY: 'cluster',
            'id': value.id,
            'name': value.name,
            'environment': value.environment,
            'status': value.status,
        }
    if is_dataclass(value) and not isinstance(value, type):
        return encode_value(asdict(value))
    if isinstance(value, Cluster):
        reference = cluster_reference_from_model(value)
        return {
            _TYPE_KEY: 'cluster',
            'id': reference.id,
            'name': reference.name,
            'environment': reference.environment,
            'status': reference.status,
        }
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
        cluster_id = str(value.get('id') or '')
        if not cluster_id:
            return None
        if value.get('name') is not None:
            return ClusterReference(
                id=cluster_id,
                name=str(value.get('name') or 'Unknown Cluster'),
                environment=str(value.get('environment') or ''),
                status=str(value.get('status') or 'unknown'),
            )
        # Backward compatibility for snapshots generated before cluster metadata
        # was embedded in the payload. Load scalar columns only; never return an
        # ORM model to the read-only presentation context.
        return load_cluster_reference(cluster_id)
    return {key: decode_value(item) for key, item in value.items()}
