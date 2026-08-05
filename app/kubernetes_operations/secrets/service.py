"""Application services for Kubernetes Secret operational workflows.

The landing-page overview reads only the latest Configuration Inventory
snapshot. Live Kubernetes API access is reserved for explicit user-requested
validation and mutation workflows.
"""

from __future__ import annotations

from sqlalchemy import func

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.governance.tls_certificates.service import (
    apply_bulk_update,
    apply_certificate_update,
    get_tls_certificate_detail,
    get_tls_certificate_page,
    preview_uploaded_pair,
)
from app.models import ConfigurationInventory


def get_secret_management_overview() -> dict[str, int]:
    """Return snapshot-backed Secret totals for the landing-page hero."""

    query = filter_current_generation(ConfigurationInventory.query, ConfigurationInventory).filter_by(
        object_type='Secret'
    )
    total = query.count()
    namespace_count = (
        query.with_entities(func.count(func.distinct(ConfigurationInventory.namespace))).scalar() or 0
    )
    cluster_count = (
        db.session.query(func.count(func.distinct(ConfigurationInventory.cluster_id))).filter(secret_filter).scalar()
        or 0
    )
    tls_count = (
        db.session.query(func.count(ConfigurationInventory.id))
        .filter(
            secret_filter,
            ConfigurationInventory.secret_type == 'kubernetes.io/tls',
        )
        .scalar()
        or 0
    )

    return {
        'total': int(total),
        'tls_count': int(tls_count),
        'namespace_count': int(namespace_count),
        'cluster_count': int(cluster_count),
    }


__all__ = [
    'apply_bulk_update',
    'apply_certificate_update',
    'get_secret_management_overview',
    'get_tls_certificate_detail',
    'get_tls_certificate_page',
    'preview_uploaded_pair',
]
