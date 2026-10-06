from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.models import (
    Cluster,
    ClusterInventory,
    ConfigurationInventory,
    IngressInventory,
    NamespaceInventory,
    NodeInventory,
    PodInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)

INVENTORY_FRESHNESS_HOURS = 24

INVENTORY_ASSET_LABELS = {
    'nodes': 'Nodes',
    'namespaces': 'Namespaces',
    'workloads': 'Workloads',
    'pods': 'Pods',
    'services': 'Services',
    'ingresses': 'Ingresses',
    'storage': 'Storage',
    'configuration': 'Configuration',
}


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_stale_inventory(value: datetime | None) -> bool:
    collected_at = _normalize_datetime(value)
    if collected_at is None:
        return False
    age = datetime.now(UTC) - collected_at
    return age.total_seconds() > INVENTORY_FRESHNESS_HOURS * 3600


def _build_inventory_signals(
    *,
    connected: bool,
    synced_at: datetime | None,
    node_count: int,
    workload_count: int,
    pod_count: int,
    storage_count: int,
) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []

    if not connected:
        signals.append(
            {
                'label': 'Connection Risk',
                'tone': 'critical',
                'icon': 'plug-zap',
                'description': (
                    'The cluster connection is unavailable, so future inventory updates cannot be confirmed.'
                ),
            }
        )

    if synced_at is None:
        signals.append(
            {
                'label': 'Never Collected',
                'tone': 'warning',
                'icon': 'database-zap',
                'description': ('No committed inventory snapshot is available for this cluster.'),
            }
        )
    elif _is_stale_inventory(synced_at):
        signals.append(
            {
                'label': 'Stale Snapshot',
                'tone': 'warning',
                'icon': 'clock-alert',
                'description': (
                    f'The latest snapshot is older than the {INVENTORY_FRESHNESS_HOURS}-hour freshness window.'
                ),
            }
        )

    if pod_count >= 100 or workload_count >= 50:
        signals.append(
            {
                'label': 'High Density',
                'tone': 'info',
                'icon': 'boxes',
                'description': (
                    'The cluster contains a high number of pods or workloads and may need closer inventory review.'
                ),
            }
        )

    if node_count > 0 and storage_count == 0:
        signals.append(
            {
                'label': 'No Storage Data',
                'tone': 'unknown',
                'icon': 'hard-drive',
                'description': ('Node inventory exists, but no current storage inventory records were collected.'),
            }
        )

    return signals[:3]


def _inventory_guidance(
    *,
    connected: bool,
    synced_at: datetime | None,
    signals: list[dict[str, str]],
) -> dict[str, str]:
    if not connected:
        return {
            'title': 'Restore Cluster Connection',
            'description': (
                'Reconnect the cluster before relying on future inventory updates or '
                'using this snapshot for operational decisions.'
            ),
            'tone': 'critical',
            'icon': 'plug-zap',
        }
    if synced_at is None:
        return {
            'title': 'Run the First Inventory Sync',
            'description': (
                'Create the first committed inventory snapshot before reviewing asset '
                'coverage or cluster-level inventory posture.'
            ),
            'tone': 'warning',
            'icon': 'database-zap',
        }
    if _is_stale_inventory(synced_at):
        return {
            'title': 'Refresh the Inventory Snapshot',
            'description': (
                f'Run Inventory Sync because this snapshot is older than the '
                f'{INVENTORY_FRESHNESS_HOURS}-hour freshness window.'
            ),
            'tone': 'warning',
            'icon': 'refresh-cw',
        }
    if signals:
        return {
            'title': 'Review Inventory Signals',
            'description': (
                'Open the relevant asset inventory to validate the highlighted conditions before planning changes.'
            ),
            'tone': 'info',
            'icon': 'scan-search',
        }
    return {
        'title': 'Snapshot Ready for Review',
        'description': (
            'The committed snapshot is current and no inventory signals require immediate '
            'attention. Continue to an asset inventory for object-level review.'
        ),
        'tone': 'normal',
        'icon': 'circle-check',
    }


def get_cluster_by_id(cluster_id: str) -> Cluster | None:
    return db.session.get(Cluster, cluster_id)


def get_inventory_clusters() -> list[Cluster]:
    return Cluster.query.order_by(
        Cluster.created_at.asc(),
        Cluster.id.asc(),
    ).all()


def _grouped_current_counts(model: Any, cluster_ids: list[Any]) -> dict[Any, int]:
    if not cluster_ids:
        return {}

    query = db.session.query(model.cluster_id, func.count(model.id))
    query = filter_current_generation(query, model)
    return {
        cluster_id: int(count or 0)
        for cluster_id, count in (query.filter(model.cluster_id.in_(cluster_ids)).group_by(model.cluster_id).all())
    }


def get_inventory_cluster_summary() -> tuple[
    list[Cluster],
    dict[str, dict[str, Any]],
]:
    clusters = get_inventory_clusters()
    cluster_ids = [cluster.id for cluster in clusters]

    inventories: dict[str, ClusterInventory] = {}
    namespace_counts = _grouped_current_counts(NamespaceInventory, cluster_ids)

    if cluster_ids:
        inventories = {
            inventory.cluster_id: inventory
            for inventory in ClusterInventory.query.filter(ClusterInventory.cluster_id.in_(cluster_ids)).all()
        }

    summary: dict[str, dict[str, Any]] = {}
    for cluster in clusters:
        inventory = inventories.get(cluster.id)
        summary[cluster.id] = {
            'version': inventory.kubernetes_version if inventory else '-',
            'namespaces': namespace_counts.get(cluster.id, 0),
            'synced_at': inventory.collected_at if inventory else None,
            'collection_evidence': dict(inventory.collection_evidence or {}) if inventory else {},
        }

    return clusters, summary


def _sync_status(synced_at: datetime | None) -> tuple[str, str]:
    if synced_at is None:
        return 'Never Collected', 'warning'
    if _is_stale_inventory(synced_at):
        return 'Stale', 'warning'
    return 'Current', 'normal'


def _selected_freshness_scope(
    clusters: list[Cluster],
    summary: dict[str, dict[str, Any]],
    cluster_id: str,
) -> tuple[list[Cluster], list[datetime], list[tuple[str, str, str]]]:
    selected = [cluster for cluster in clusters if not cluster_id or str(cluster.id) == str(cluster_id)]
    committed = [
        value
        for cluster in selected
        if (value := _normalize_datetime(summary.get(cluster.id, {}).get('synced_at'))) is not None
    ]
    exceptions = [
        (cluster.name, family, state)
        for cluster in selected
        for family, state in (summary.get(cluster.id, {}).get('collection_evidence') or {}).items()
        if state != 'Collected'
    ]
    return selected, committed, exceptions


def _freshness_posture(
    *,
    selected_count: int,
    committed_count: int,
    stale_count: int,
    missing_count: int,
    collection_exception_count: int,
) -> tuple[str, str, str]:
    if selected_count == 0:
        return 'No Scope', 'unknown', 'No registered Kubernetes cluster matches the selected inventory scope.'
    if committed_count == 0:
        description = (
            'No committed snapshot is available for the selected cluster.'
            if selected_count == 1
            else 'No committed snapshots are available for the selected fleet scope.'
        )
        return 'Not Collected', 'warning', description
    if stale_count or missing_count or collection_exception_count:
        description = (
            'The selected cluster snapshot needs freshness or collection review.'
            if selected_count == 1
            else (
                f'{committed_count} of {selected_count} cluster snapshots are committed; '
                'review stale, missing, or partial collection evidence.'
            )
        )
        return 'Review Freshness', 'warning', description
    description = (
        'The selected cluster snapshot is current and fully committed.'
        if selected_count == 1
        else f'All {selected_count} cluster snapshots are current and fully committed.'
    )
    return 'Current', 'normal', description


def _freshness_coverage(selected_count: int, committed_count: int) -> tuple[str, str, str]:
    if selected_count == 0:
        return 'No active scope', 'Select a registered cluster', 'unknown'
    label = f'{committed_count} of {selected_count} snapshots'
    if committed_count == selected_count:
        return label, 'Fully committed', 'normal'
    if committed_count:
        return label, 'Partially committed', 'warning'
    return label, 'No committed data', 'warning'


def _freshness_exception_label(stale_count: int, missing_count: int, collection_count: int) -> str:
    parts = [
        f'{count} {label}'
        for count, label in (
            (stale_count, 'Stale'),
            (missing_count, 'Missing'),
            (collection_count, 'Collection'),
        )
        if count
    ]
    return ' · '.join(parts) if parts else 'No Exceptions'


def get_inventory_freshness_context(cluster_id: str = '') -> dict[str, Any]:
    """Describe when the committed inventory snapshot for the current scope was collected."""
    clusters, summary = get_inventory_cluster_summary()
    selected, committed, collection_exceptions = _selected_freshness_scope(clusters, summary, cluster_id)
    selected_count = len(selected)
    committed_count = len(committed)
    latest = max(committed) if committed else None
    oldest = min(committed) if committed else None
    missing_count = max(selected_count - committed_count, 0)
    stale_count = sum(_is_stale_inventory(value) for value in committed)
    collection_exception_count = len(collection_exceptions)
    status, tone, description = _freshness_posture(
        selected_count=selected_count,
        committed_count=committed_count,
        stale_count=stale_count,
        missing_count=missing_count,
        collection_exception_count=collection_exception_count,
    )
    coverage_label, coverage_supporting, coverage_tone = _freshness_coverage(
        selected_count,
        committed_count,
    )
    has_exceptions = bool(stale_count or missing_count or collection_exception_count)
    exception_label = _freshness_exception_label(stale_count, missing_count, collection_exception_count)

    return {
        'latest_collected_at': latest,
        'oldest_collected_at': oldest,
        'cluster_count': selected_count,
        'committed_count': committed_count,
        'missing_count': missing_count,
        'stale_count': stale_count,
        'collection_exception_count': collection_exception_count,
        'collection_exceptions': collection_exceptions,
        'freshness_window_hours': INVENTORY_FRESHNESS_HOURS,
        'scope_label': selected[0].name if selected_count == 1 else f'{selected_count} Clusters',
        'scope_supporting': 'Selected cluster'
        if selected_count == 1
        else ('Fleet scope' if selected_count else 'No active scope'),
        'latest_supporting': f'{INVENTORY_FRESHNESS_HOURS}-hour freshness window'
        if latest
        else 'No committed timestamp',
        'status': status,
        'tone': tone,
        'description': description,
        'source_label': 'Committed Inventory Snapshot',
        'coverage_label': coverage_label,
        'coverage_supporting': coverage_supporting,
        'coverage_tone': coverage_tone,
        'exception_label': exception_label,
        'exceptions_supporting': 'Review required' if has_exceptions else 'No issues detected',
        'exceptions_tone': 'warning' if has_exceptions else 'normal',
    }


def _asset_catalog(totals: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {
            'key': 'nodes',
            'title': 'Nodes',
            'count': totals['nodes'],
            'icon': 'cpu',
            'description': 'Worker and control-plane capacity.',
            'endpoint': 'inventory.nodes',
        },
        {
            'key': 'namespaces',
            'title': 'Namespaces',
            'count': totals['namespaces'],
            'icon': 'folder-tree',
            'description': 'Tenant and application scopes.',
            'endpoint': 'inventory.namespaces',
        },
        {
            'key': 'workloads',
            'title': 'Workloads',
            'count': totals['workloads'],
            'icon': 'boxes',
            'description': 'Deployments and workload controllers.',
            'endpoint': 'inventory.workloads',
        },
        {
            'key': 'pods',
            'title': 'Pods',
            'count': totals['pods'],
            'icon': 'container',
            'description': 'Current runtime workload instances.',
            'endpoint': 'inventory.pods',
        },
        {
            'key': 'services',
            'title': 'Services',
            'count': totals['services'],
            'icon': 'network',
            'description': 'Cluster networking endpoints.',
            'endpoint': 'inventory.services',
        },
        {
            'key': 'ingresses',
            'title': 'Ingresses',
            'count': totals['ingresses'],
            'icon': 'route',
            'description': 'Published application entry points.',
            'endpoint': 'inventory.ingresses',
        },
        {
            'key': 'storage',
            'title': 'Storage',
            'count': totals['storage'],
            'icon': 'hard-drive',
            'description': 'Storage classes, volumes, and claims.',
            'endpoint': 'inventory.storage',
        },
        {
            'key': 'configuration',
            'title': 'Configuration',
            'count': totals['configuration'],
            'icon': 'file-cog',
            'description': 'ConfigMaps and Secret metadata.',
            'endpoint': 'inventory.configuration',
        },
    ]


def get_inventory_overview() -> dict[str, Any]:
    clusters, inventory_summary = get_inventory_cluster_summary()
    cluster_ids = [cluster.id for cluster in clusters]

    count_maps = {
        'nodes': _grouped_current_counts(NodeInventory, cluster_ids),
        'namespaces': _grouped_current_counts(NamespaceInventory, cluster_ids),
        'workloads': _grouped_current_counts(WorkloadInventory, cluster_ids),
        'pods': _grouped_current_counts(PodInventory, cluster_ids),
        'services': _grouped_current_counts(ServiceInventory, cluster_ids),
        'ingresses': _grouped_current_counts(IngressInventory, cluster_ids),
        'storage': _grouped_current_counts(StorageInventory, cluster_ids),
        'configuration': _grouped_current_counts(ConfigurationInventory, cluster_ids),
    }

    cluster_rows: list[dict[str, Any]] = []
    for cluster in clusters:
        summary = inventory_summary.get(cluster.id, {})
        synced_at = summary.get('synced_at')
        counts = {key: values.get(cluster.id, 0) for key, values in count_maps.items()}
        total_objects = sum(counts.values())
        sync_label, sync_tone = _sync_status(synced_at)
        connected = cluster.status == 'connected'
        signals = _build_inventory_signals(
            connected=connected,
            synced_at=synced_at,
            node_count=counts['nodes'],
            workload_count=counts['workloads'],
            pod_count=counts['pods'],
            storage_count=counts['storage'],
        )
        populated_asset_types = sum(1 for count in counts.values() if count > 0)
        dominant_asset_key = max(counts, key=lambda asset_key: counts[asset_key]) if total_objects else None
        dominant_asset = (
            {
                'label': INVENTORY_ASSET_LABELS[dominant_asset_key],
                'count': counts[dominant_asset_key],
            }
            if dominant_asset_key
            else {'label': 'No Assets', 'count': 0}
        )

        cluster_rows.append(
            {
                'id': cluster.id,
                'name': cluster.name,
                'environment': cluster.environment,
                'status': cluster.status,
                'kubernetes_version': summary.get('version') or '-',
                'synced_at': synced_at,
                'sync_status_label': sync_label,
                'sync_status_tone': sync_tone,
                'counts': counts,
                'total_objects': total_objects,
                'signals': signals,
                'populated_asset_types': populated_asset_types,
                'dominant_asset': dominant_asset,
                'snapshot_source': 'Committed Snapshot',
                'freshness_window_hours': INVENTORY_FRESHNESS_HOURS,
                'guidance': _inventory_guidance(
                    connected=connected,
                    synced_at=synced_at,
                    signals=signals,
                ),
            }
        )

    totals = {
        'clusters': _count_rows(Cluster),
        'nodes': _count_rows(NodeInventory),
        'namespaces': _count_rows(NamespaceInventory),
        'workloads': _count_rows(WorkloadInventory),
        'pods': _count_rows(PodInventory),
        'services': _count_rows(ServiceInventory),
        'ingresses': _count_rows(IngressInventory),
        'storage': _count_rows(StorageInventory),
        'configuration': _count_rows(ConfigurationInventory),
    }
    inventory_total = sum(value for key, value in totals.items() if key != 'clusters')
    asset_catalog = _asset_catalog(totals)
    active_signal_count = sum(len(cluster['signals']) for cluster in cluster_rows)
    health = get_inventory_health()
    total_clusters = totals['clusters']
    posture_status = (
        'Unknown' if total_clusters == 0 else 'Healthy' if health['healthy_clusters'] == total_clusters else 'Attention'
    )
    posture_tone = 'unknown' if posture_status == 'Unknown' else 'normal' if posture_status == 'Healthy' else 'warning'

    return {
        'total_clusters': totals['clusters'],
        'total_nodes': totals['nodes'],
        'total_namespaces': totals['namespaces'],
        'total_workloads': totals['workloads'],
        'total_pods': totals['pods'],
        'total_services': totals['services'],
        'total_ingresses': totals['ingresses'],
        'total_storage': totals['storage'],
        'total_configuration': totals['configuration'],
        'inventory_total': inventory_total,
        'asset_catalog': asset_catalog,
        'active_signal_count': active_signal_count,
        'clusters': cluster_rows,
        'inventory_summary': inventory_summary,
        'health': health,
        'posture': {
            'status': posture_status,
            'tone': posture_tone,
        },
    }


def get_inventory_overview_cluster_detail(cluster_id: str) -> dict[str, Any] | None:
    """Return one committed cluster-inventory overview row for detail presentation."""
    normalized_id = str(cluster_id)
    return next(
        (cluster for cluster in get_inventory_overview()['clusters'] if str(cluster['id']) == normalized_id),
        None,
    )


def _count_rows(model: Any) -> int:
    query = db.session.query(func.count(model.id))
    if model is not Cluster:
        query = filter_current_generation(query, model)
    return query.scalar() or 0


def get_inventory_health() -> dict[str, Any]:
    clusters = Cluster.query.all()
    total_clusters = len(clusters)
    healthy_clusters = 0
    never_synced = 0
    stale_synced = 0
    fresh_synced = 0
    last_sync = None
    connected_clusters = 0

    inventory_by_cluster = (
        {
            inventory.cluster_id: inventory
            for inventory in ClusterInventory.query.filter(
                ClusterInventory.cluster_id.in_([cluster.id for cluster in clusters])
            ).all()
        }
        if clusters
        else {}
    )

    for cluster in clusters:
        connected = cluster.status == 'connected'
        if connected:
            connected_clusters += 1

        inventory = inventory_by_cluster.get(cluster.id)
        if inventory is None:
            never_synced += 1
            continue

        collected_at = _normalize_datetime(inventory.collected_at)
        if _is_stale_inventory(collected_at):
            stale_synced += 1
        else:
            fresh_synced += 1
            if connected:
                healthy_clusters += 1

        if collected_at and (last_sync is None or collected_at > last_sync):
            last_sync = collected_at

    synced_clusters = total_clusters - never_synced
    disconnected_clusters = total_clusters - connected_clusters

    def percentage(value: int) -> int:
        return round((value / total_clusters) * 100) if total_clusters else 0

    return {
        'connected_clusters': connected_clusters,
        'healthy_clusters': healthy_clusters,
        'never_synced': never_synced,
        'stale_synced': stale_synced,
        'fresh_synced': fresh_synced,
        'synced_clusters': synced_clusters,
        'disconnected_clusters': disconnected_clusters,
        'coverage_score': percentage(synced_clusters),
        'connection_score': percentage(connected_clusters),
        'freshness_score': percentage(fresh_synced),
        'freshness_window_hours': INVENTORY_FRESHNESS_HOURS,
        'last_sync': last_sync,
    }
