"""Application services for Kubernetes Secret operational workflows.

The landing-page overview reads only the latest Configuration Inventory
snapshot. Live Kubernetes API access is reserved for explicit user-requested
validation and mutation workflows.
"""

from __future__ import annotations

from app.common.inventory_generation import filter_current_generation
from app.models import ConfigurationInventory


def get_secret_management_overview() -> dict[str, int]:
    """Return Secret totals from the latest committed Configuration generation."""

    query = filter_current_generation(ConfigurationInventory.query, ConfigurationInventory).filter_by(
        object_type='Secret'
    )
    total = query.count()
    namespace_count = query.with_entities(ConfigurationInventory.namespace).distinct().count()
    cluster_count = query.with_entities(ConfigurationInventory.cluster_id).distinct().count()
    tls_count = query.filter(ConfigurationInventory.secret_type == 'kubernetes.io/tls').count()

    return {
        'total': int(total),
        'tls_count': int(tls_count),
        'namespace_count': int(namespace_count),
        'cluster_count': int(cluster_count),
    }
