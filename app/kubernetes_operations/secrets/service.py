"""Application services for Kubernetes Secret operational workflows.

The landing-page overview reads only the latest Configuration Inventory
snapshot. Live Kubernetes API access is reserved for explicit user-requested
validation and mutation workflows.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from sqlalchemy import func

from app.extensions import db
from app.models import ConfigurationInventory
from app.governance.tls_certificates.service import (
    apply_bulk_update,
    apply_certificate_update,
    get_tls_certificate_detail,
    get_tls_certificate_page,
    preview_uploaded_pair,
)

_SECRET_TYPE_PRESENTATION: OrderedDict[str, tuple[str, str]] = OrderedDict(
    [
        ('Opaque', ('Opaque', '#2563eb')),
        ('kubernetes.io/tls', ('TLS', '#7c3aed')),
        ('kubernetes.io/dockerconfigjson', ('Registry', '#0891b2')),
        ('kubernetes.io/basic-auth', ('Basic Auth', '#d97706')),
        ('kubernetes.io/ssh-auth', ('SSH', '#059669')),
    ]
)
_OTHER_TYPE_COLOR = '#64748b'


def _normalized_secret_type(value: str | None) -> str:
    normalized = (value or 'Opaque').strip()
    return normalized or 'Opaque'


def get_secret_management_overview() -> dict[str, Any]:
    """Return snapshot-backed Secret totals and type distribution."""

    secret_filter = ConfigurationInventory.object_type == 'Secret'
    total = (
        db.session.query(func.count(ConfigurationInventory.id))
        .filter(secret_filter)
        .scalar()
        or 0
    )
    namespace_count = (
        db.session.query(func.count(func.distinct(ConfigurationInventory.namespace)))
        .filter(secret_filter)
        .scalar()
        or 0
    )
    cluster_count = (
        db.session.query(func.count(func.distinct(ConfigurationInventory.cluster_id)))
        .filter(secret_filter)
        .scalar()
        or 0
    )
    latest_collected_at = (
        db.session.query(func.max(ConfigurationInventory.collected_at))
        .filter(secret_filter)
        .scalar()
    )
    rows = (
        db.session.query(
            ConfigurationInventory.secret_type,
            func.count(ConfigurationInventory.id),
        )
        .filter(secret_filter)
        .group_by(ConfigurationInventory.secret_type)
        .all()
    )

    counts = {
        _normalized_secret_type(secret_type): int(count or 0)
        for secret_type, count in rows
    }
    distribution: list[dict[str, Any]] = []
    accounted_types: set[str] = set()

    for secret_type, (label, color) in _SECRET_TYPE_PRESENTATION.items():
        count = counts.get(secret_type, 0)
        accounted_types.add(secret_type)
        if count:
            distribution.append(
                {
                    'key': secret_type,
                    'label': label,
                    'count': count,
                    'percentage': round((count / total) * 100, 1) if total else 0,
                    'color': color,
                }
            )

    other_count = sum(
        count for secret_type, count in counts.items() if secret_type not in accounted_types
    )
    if other_count:
        distribution.append(
            {
                'key': 'other',
                'label': 'Other',
                'count': other_count,
                'percentage': round((other_count / total) * 100, 1) if total else 0,
                'color': _OTHER_TYPE_COLOR,
            }
        )

    distribution.sort(key=lambda item: item['count'], reverse=True)
    tls_count = counts.get('kubernetes.io/tls', 0)
    most_used = distribution[0] if distribution else None

    return {
        'total': int(total),
        'tls_count': int(tls_count),
        'namespace_count': int(namespace_count),
        'cluster_count': int(cluster_count),
        'latest_collected_at': latest_collected_at,
        'distribution': distribution,
        'most_used': most_used,
        'has_snapshot': bool(total),
    }


__all__ = [
    'apply_bulk_update',
    'apply_certificate_update',
    'get_secret_management_overview',
    'get_tls_certificate_detail',
    'get_tls_certificate_page',
    'preview_uploaded_pair',
]
