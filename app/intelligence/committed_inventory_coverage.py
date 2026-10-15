"""Intelligence inventory evidence qualification from committed KAORI state only.

Shared read-model authority for Overview and Recommendations; no provider I/O,
approval mutation or reciprocal Overview/Service module imports.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.integration import IntegrationInstance
from app.models.inventory import ClusterInventory
from app.models.object_storage import ObjectStorageSystem
from app.models.registry import RegistryCollectionState


def _evidence_coverage() -> dict[str, Any]:
    """Qualified 24-hour inventory baseline, not a claim that all evaluators are healthy.

    This keeps the normal landing page committed/SQL-only. Security and analytics
    capability availability remain owned by the originating domain.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=1)
    kubernetes_total = Cluster.query.count()
    kubernetes_current = int(
        db.session.query(func.count(Cluster.id))
        .filter(
            db.session.query(ClusterInventory.id)
            .filter(
                ClusterInventory.cluster_id == Cluster.id,
                ClusterInventory.collected_at >= cutoff,
                ClusterInventory.collected_at <= now,
            )
            .exists()
        )
        .scalar()
        or 0
    )
    storage_total = ObjectStorageSystem.query.count()
    storage_current = ObjectStorageSystem.query.filter(
        ObjectStorageSystem.inventory_observed_at >= cutoff,
        ObjectStorageSystem.inventory_observed_at <= now,
    ).count()
    registry_scope = IntegrationInstance.query.filter(
        IntegrationInstance.integration_type == 'registry',
        IntegrationInstance.enabled.is_(True),
        IntegrationInstance.lifecycle_status == 'active',
    )
    registry_total = registry_scope.count()
    registry_current = int(
        registry_scope.join(
            RegistryCollectionState,
            RegistryCollectionState.integration_instance_id == IntegrationInstance.id,
        )
        .filter(
            RegistryCollectionState.status == 'ready',
            RegistryCollectionState.last_committed_at >= cutoff,
            RegistryCollectionState.last_committed_at <= now,
        )
        .count()
    )
    by_domain = {
        'kubernetes': {'total': kubernetes_total, 'recent': kubernetes_current},
        'object_storage': {'total': storage_total, 'recent': storage_current},
        'registry': {'total': registry_total, 'recent': registry_current},
    }
    total = sum(item['total'] for item in by_domain.values())
    recent = sum(item['recent'] for item in by_domain.values())
    return {
        **by_domain,
        'total': total,
        'recent': recent,
        'missing_or_stale': total - recent,
        'complete': bool(total) and recent == total,
        'lookback_hours': 24,
    }
