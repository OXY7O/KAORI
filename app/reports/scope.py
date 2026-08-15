from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.object_storage import ObjectStorageSystem

KUBERNETES_CLUSTER_ASSET_TYPE = 'kubernetes_cluster'
OBJECT_STORAGE_SYSTEM_ASSET_TYPE = 'object_storage_system'


@dataclass(frozen=True, slots=True)
class ReportScope:
    asset_type: str
    asset_id: str
    label: str
    domain: str
    source_kind: str
    namespace: str | None = None

    @property
    def scope_label(self) -> str:
        if self.asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
            return 'Object Storage System'
        return 'Kubernetes Cluster'

    @property
    def secondary_label(self) -> str:
        if self.asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
            return 'System Scope'
        return self.namespace or 'All Namespaces'


def resolve_report_scope(record: Any) -> ReportScope | None:
    asset_type = str(getattr(record, 'scope_asset_type', '') or '').strip()
    asset_id = str(getattr(record, 'scope_asset_id', '') or '').strip()
    snapshot = str(getattr(record, 'scope_asset_label_snapshot', '') or '').strip()
    domain = str(getattr(record, 'report_domain', '') or 'kubernetes').strip()
    source_kind = str(getattr(record, 'source_kind', '') or domain).strip()

    # Backward compatibility for reports created before generic report scope.
    cluster_id = str(getattr(record, 'cluster_id', '') or '').strip()
    if not asset_type and cluster_id:
        asset_type = KUBERNETES_CLUSTER_ASSET_TYPE
        asset_id = cluster_id

    if asset_type == KUBERNETES_CLUSTER_ASSET_TYPE:
        if not asset_id:
            return None
        cluster = None if snapshot else db.session.get(Cluster, asset_id)
        label = snapshot or (str(cluster.name) if cluster is not None else asset_id)
        return ReportScope(
            asset_type=asset_type,
            asset_id=asset_id,
            label=label,
            domain=domain or 'kubernetes',
            source_kind=source_kind or 'kubernetes',
            namespace=str(getattr(record, 'namespace', '') or '').strip() or None,
        )

    if asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
        if not asset_id:
            return None
        system = None if snapshot else db.session.get(ObjectStorageSystem, asset_id)
        label = snapshot or (str(system.name) if system is not None else asset_id)
        return ReportScope(
            asset_type=asset_type,
            asset_id=asset_id,
            label=label,
            domain=domain or 'object_storage',
            source_kind=source_kind or 'object_storage',
        )

    if asset_type and asset_id:
        return ReportScope(
            asset_type=asset_type,
            asset_id=asset_id,
            label=snapshot or asset_id,
            domain=domain,
            source_kind=source_kind,
            namespace=str(getattr(record, 'namespace', '') or '').strip() or None,
        )
    return None


def scope_asset_label(record: Any, *, fallback: str = 'Scope Unavailable') -> str:
    scope = resolve_report_scope(record)
    return scope.label if scope is not None else fallback


def scope_asset_type(record: Any) -> str:
    scope = resolve_report_scope(record)
    return scope.asset_type if scope is not None else ''
