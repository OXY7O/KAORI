from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any

import yaml
from sqlalchemy import func, or_

from app.alertmanager.resolver import resolve_alertmanager_sources
from app.extensions.db import db
from app.integrations.deletion import DeletionBlocked, kubernetes_deletion_guard
from app.integrations.kubernetes.resolver import connection_for_cluster
from app.integrations.kubernetes.validation import test_cluster_connection, test_cluster_runtime_health
from app.jobs.service import acquire_resource_admission_locks
from app.models import Cluster, ClusterInventory, ClusterStatus, NamespaceInventory, Report, ReportSchedule
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.kubernetes import KubernetesConnection
from app.metrics.repository import resolve_instance_for_cluster

DEFAULT_CLUSTER_PER_PAGE = 5
CLUSTER_PER_PAGE_OPTIONS = [
    5,
    10,
    25,
    50,
]


@dataclass(frozen=True)
class ClusterPagination:
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_prev: bool
    has_next: bool
    prev_page: int
    next_page: int
    start_item: int
    end_item: int


def parse_kubeconfig(kubeconfig: str) -> dict[str, str]:
    try:
        parsed_config = yaml.safe_load(kubeconfig)
    except yaml.YAMLError as exc:
        raise ValueError('Invalid kubeconfig format') from exc

    if not isinstance(parsed_config, dict):
        raise ValueError('Invalid kubeconfig format')

    clusters = parsed_config.get('clusters')

    if not isinstance(clusters, list) or len(clusters) == 0:
        raise ValueError('Kubeconfig does not contain any cluster definition')

    first_cluster = clusters[0]

    if not isinstance(first_cluster, dict):
        raise ValueError('Invalid kubeconfig cluster definition')

    cluster_data = first_cluster.get('cluster')

    if not isinstance(cluster_data, dict):
        raise ValueError('Invalid kubeconfig cluster data')

    server = cluster_data.get('server')

    if not isinstance(server, str) or not server.strip():
        raise ValueError('Kubeconfig cluster server is missing')

    return {
        'server': server.strip(),
    }


def normalize_page(
    value: str | int | None,
) -> int:
    try:
        page = int(
            value or 1,
        )
    except (
        TypeError,
        ValueError,
    ):
        return 1

    return max(
        page,
        1,
    )


def normalize_per_page(
    value: str | int | None,
) -> int:
    try:
        per_page = int(
            value or DEFAULT_CLUSTER_PER_PAGE,
        )
    except (
        TypeError,
        ValueError,
    ):
        return DEFAULT_CLUSTER_PER_PAGE

    if per_page not in CLUSTER_PER_PAGE_OPTIONS:
        return DEFAULT_CLUSTER_PER_PAGE

    return per_page


def normalize_search(
    value: str | None,
) -> str:
    return (value or '').strip()


def normalize_environment(
    value: str | None,
) -> str:
    environment = (value or 'all').strip().lower()

    if not environment:
        return 'all'

    return environment


def get_filtered_cluster_query(
    *,
    search: str,
    environment: str,
):
    query = Cluster.query.outerjoin(
        KubernetesConnection,
        KubernetesConnection.cluster_id == Cluster.id,
    )

    if environment != 'all':
        query = query.filter(
            func.lower(
                Cluster.environment,
            )
            == environment,
        )

    if search:
        like_pattern = f'%{search}%'
        query = query.filter(
            or_(
                Cluster.name.ilike(
                    like_pattern,
                ),
                Cluster.environment.ilike(
                    like_pattern,
                ),
                KubernetesConnection.server.ilike(
                    like_pattern,
                ),
                Cluster.status.ilike(
                    like_pattern,
                ),
            )
        )

    return query


def build_pagination(
    *,
    page: int,
    per_page: int,
    total_items: int,
) -> ClusterPagination:
    total_pages = max(
        ceil(
            total_items / per_page,
        ),
        1,
    )

    page = min(
        page,
        total_pages,
    )

    if total_items == 0:
        start_item = 0
        end_item = 0
    else:
        start_item = ((page - 1) * per_page) + 1
        end_item = min(
            page * per_page,
            total_items,
        )

    return ClusterPagination(
        page=page,
        per_page=per_page,
        total_items=total_items,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        prev_page=max(
            page - 1,
            1,
        ),
        next_page=min(
            page + 1,
            total_pages,
        ),
        start_item=start_item,
        end_item=end_item,
    )


def get_cluster_summary(
    *,
    page: int,
    per_page: int,
    search: str,
    environment: str,
) -> tuple[list[Cluster], dict[str, dict[str, Any]], ClusterPagination]:
    query = get_filtered_cluster_query(
        search=search,
        environment=environment,
    ).order_by(
        Cluster.created_at.desc(),
    )

    total_items = query.count()
    pagination = build_pagination(
        page=page,
        per_page=per_page,
        total_items=total_items,
    )

    clusters = (
        query.offset(
            (pagination.page - 1) * pagination.per_page,
        )
        .limit(
            pagination.per_page,
        )
        .all()
    )

    cluster_ids = [cluster.id for cluster in clusters]

    inventories = {}

    if cluster_ids:
        inventories = {
            inventory.cluster_id: inventory
            for inventory in ClusterInventory.query.filter(
                ClusterInventory.cluster_id.in_(
                    cluster_ids,
                )
            ).all()
        }

    namespace_counts = {}

    if cluster_ids:
        namespace_counts = {
            cluster_id: count
            for cluster_id, count in (
                db.session.query(
                    NamespaceInventory.cluster_id,
                    func.count(
                        NamespaceInventory.id,
                    ),
                )
                .filter(
                    NamespaceInventory.cluster_id.in_(
                        cluster_ids,
                    )
                )
                .group_by(
                    NamespaceInventory.cluster_id,
                )
                .all()
            )
        }

    inventory_summary: dict[str, dict[str, Any]] = {}

    for cluster in clusters:
        inventory = inventories.get(
            cluster.id,
        )
        connection = cluster.kubernetes_connection

        inventory_summary[cluster.id] = {
            'version': (connection.detected_version if connection else None)
            or (inventory.kubernetes_version if inventory else '-'),
            'compatibility_status': (connection.compatibility_status if connection else None) or 'not_checked',
            'readiness_status': (connection.readiness_status if connection else None) or 'not_checked',
            'lifecycle_status': (connection.lifecycle_status if connection else None) or 'unknown',
            'api_profile': (connection.compatibility_profile if connection else None) or 'not_checked',
            'namespaces': namespace_counts.get(
                cluster.id,
                0,
            ),
            'synced_at': inventory.collected_at if inventory else None,
        }

    return clusters, inventory_summary, pagination


def get_alertmanager_summary(
    cluster_ids: list[str],
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for cluster_id in cluster_ids:
        resolution = resolve_alertmanager_sources(
            scope_type='kubernetes_cluster',
            scope_key=cluster_id,
        )
        selected = resolution.selected
        if selected is None:
            continue
        instance = selected.instance
        summary[cluster_id] = {
            'configured': bool(instance.endpoint),
            'connected': instance.last_status == 'connected',
            'status': instance.last_status or 'configured',
            'label': instance.display_status,
            'response_time_ms': instance.last_response_time_ms,
            'last_checked_at': instance.last_checked_at,
            'error': instance.last_error,
            'instance_id': instance.id,
            'instance_name': instance.name,
        }
    return summary


def get_metrics_source_summary(
    clusters: list[Cluster],
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for cluster in clusters:
        config = resolve_instance_for_cluster(cluster.id)
        if config is None:
            summary[cluster.id] = {
                'configured': False,
                'label': 'Not Set',
                'endpoint': None,
            }
            continue
        summary[cluster.id] = {
            'configured': bool(config.endpoint),
            'label': 'Configured' if config.endpoint else 'Not Set',
            'endpoint': config.endpoint,
        }
    return summary


def get_cluster_stats() -> dict[str, int]:
    total_clusters = Cluster.query.count()

    connected_clusters = Cluster.query.filter(
        Cluster.status == ClusterStatus.CONNECTED.value,
    ).count()

    synced_clusters = (
        db.session.query(
            ClusterInventory.cluster_id,
        )
        .distinct()
        .count()
    )

    return {
        'total_clusters': total_clusters,
        'connected_clusters': connected_clusters,
        'synced_clusters': synced_clusters,
    }


def get_cluster_by_id(cluster_id: str) -> Cluster | None:
    return db.session.get(
        Cluster,
        cluster_id,
    )


def _sync_kubernetes_runtime(
    cluster: Cluster,
    *,
    kubeconfig: str | None = None,
    server: str | None = None,
    verify_ssl: bool | None = None,
    allow_weak_tls: bool | None = None,
) -> KubernetesConnection:
    """Converge canonical identity, provider record, and asset binding.

    Cluster is the Kubernetes asset. KubernetesConnection is the only connection
    and credential authority; this function never writes provider data to Cluster.
    """
    connection = cluster.kubernetes_connection
    canonical = connection.integration_instance if connection is not None else None
    if canonical is None:
        canonical = IntegrationInstance()
        canonical.provider_type = 'kubernetes'
        canonical.name = f'{cluster.name} Kubernetes API'
        canonical.description = cluster.description
        canonical.environment = cluster.environment
        canonical.enabled = True
        canonical.readiness_status = connection.readiness_status if connection else 'validation_required'
        canonical.health_status = cluster.status
        canonical.last_checked_at = cluster.last_check
        canonical.metadata_json = {'asset_type': 'kubernetes_cluster', 'asset_key': cluster.id}
        db.session.add(canonical)
        db.session.flush()
    else:
        canonical.name = f'{cluster.name} Kubernetes API'
        canonical.description = cluster.description
        canonical.environment = cluster.environment
        canonical.readiness_status = connection.readiness_status if connection else 'validation_required'
        canonical.health_status = cluster.status
        canonical.last_checked_at = cluster.last_check

    if connection is None:
        if not kubeconfig:
            raise ValueError('Kubeconfig is required when creating a Kubernetes connection.')
        connection = KubernetesConnection()
        connection.integration_instance_id = canonical.id
        connection.cluster_id = cluster.id
        connection.kubeconfig = kubeconfig
        connection.verify_ssl = True if verify_ssl is None else bool(verify_ssl)
        connection.allow_weak_tls = False if allow_weak_tls is None else bool(allow_weak_tls)
        connection.server = server
        db.session.add(connection)
        cluster.kubernetes_connection = connection
    else:
        if kubeconfig is not None:
            connection.kubeconfig = kubeconfig
        if server is not None:
            connection.server = server
        if verify_ssl is not None:
            connection.verify_ssl = bool(verify_ssl)
        if allow_weak_tls is not None:
            connection.allow_weak_tls = bool(allow_weak_tls)

    canonical.readiness_status = connection.readiness_status or 'validation_required'
    canonical.health_status = cluster.status
    canonical.last_checked_at = cluster.last_check
    canonical.last_error = connection.validation_message

    binding = IntegrationBinding.query.filter_by(
        integration_instance_id=canonical.id,
        asset_type='kubernetes_cluster',
        asset_key=cluster.id,
        binding_role='primary',
    ).first()
    if binding is None:
        binding = IntegrationBinding()
        binding.integration_instance_id = canonical.id
        binding.asset_type = 'kubernetes_cluster'
        binding.asset_key = cluster.id
        binding.binding_role = 'primary'
        binding.priority = 100
        binding.enabled = True
        binding.capability_scope = ['inventory', 'operations', 'governance', 'discovery']
        db.session.add(binding)
    return connection


def test_cluster_draft_connection(
    *,
    kubeconfig_content: str,
    verify_ssl: bool = True,
    allow_weak_tls: bool = False,
) -> dict[str, Any]:
    """Validate reachability for a submitted kubeconfig without persistence.

    Registration testing stays intentionally lightweight. Full API discovery,
    compatibility resolution, and RBAC evidence are rebuilt by the worker after
    the connection is registered.
    """
    parsed = parse_kubeconfig(kubeconfig_content)
    return test_cluster_runtime_health(
        kubeconfig_content=kubeconfig_content,
        endpoint=parsed['server'],
        verify_ssl=verify_ssl,
        allow_weak_tls=allow_weak_tls,
    )


def create_cluster(
    name: str,
    environment: str,
    kubeconfig: str,
    description: str | None = None,
    kube_verify_ssl: bool = True,
    kube_allow_weak_tls: bool = False,
) -> Cluster:
    existing = Cluster.query.filter_by(
        name=name,
    ).first()

    if existing:
        raise ValueError('Cluster name already exists')

    result = parse_kubeconfig(
        kubeconfig,
    )
    cluster = Cluster()

    cluster.name = name
    cluster.environment = environment
    cluster.description = description

    db.session.add(
        cluster,
    )
    db.session.flush()
    _sync_kubernetes_runtime(
        cluster,
        kubeconfig=kubeconfig,
        server=result['server'],
        verify_ssl=kube_verify_ssl,
        allow_weak_tls=kube_allow_weak_tls,
    )
    db.session.commit()

    return cluster


def refresh_cluster_runtime_health(cluster: Cluster) -> dict[str, Any]:
    """Refresh lightweight API health without rebuilding capability evidence."""
    connection = connection_for_cluster(cluster)
    result = test_cluster_runtime_health(
        kubeconfig_content=connection.kubeconfig,
        endpoint=connection.server,
        verify_ssl=bool(connection.verify_ssl),
        allow_weak_tls=bool(connection.allow_weak_tls),
    )
    cluster.last_check = datetime.now(UTC)
    if result['success']:
        cluster.status = ClusterStatus.CONNECTED.value
        connection.detected_version = result.get('version') or connection.detected_version
        connection.detected_platform = result.get('platform') or connection.detected_platform
    else:
        cluster.status = ClusterStatus.FAILED.value

    # Preserve compatibility, readiness, API discovery, and capability evidence.
    _sync_kubernetes_runtime(cluster)
    db.session.commit()
    return result


def run_test_cluster(cluster: Cluster) -> dict[str, Any]:
    connection = connection_for_cluster(cluster)
    result = test_cluster_connection(
        kubeconfig_content=connection.kubeconfig,
        endpoint=connection.server,
        verify_ssl=bool(connection.verify_ssl),
        allow_weak_tls=bool(connection.allow_weak_tls),
    )

    cluster.last_check = datetime.now(
        UTC,
    )

    if result['success']:
        cluster.status = ClusterStatus.CONNECTED.value

        cluster.node_count = result.get('node_count', 0)
        connection.detected_version = result.get('version')
        connection.detected_platform = result.get('platform')
        connection.compatibility_status = result.get('compatibility_status')
        connection.compatibility_profile = result.get('compatibility_profile')
        connection.readiness_status = result.get('readiness_status')
        connection.lifecycle_status = result.get('lifecycle_status')
        connection.discovery_summary = result.get('api_discovery_summary')
        connection.validation_message = result.get('validation_message')
        connection.last_validated_at = datetime.now(UTC)

    else:
        cluster.status = ClusterStatus.FAILED.value

    _sync_kubernetes_runtime(cluster)
    db.session.commit()

    return result


def update_cluster(
    *,
    cluster: Cluster,
    name: str,
    environment: str,
    description: str | None,
    kubeconfig: str | None = None,
    kube_verify_ssl: bool = True,
    kube_allow_weak_tls: bool = False,
) -> Cluster:
    existing = Cluster.query.filter(
        Cluster.name == name,
        Cluster.id != cluster.id,
    ).first()

    if existing:
        raise ValueError('Cluster name already exists')

    connection = connection_for_cluster(cluster)
    connection_changed = bool(kubeconfig) or (
        bool(connection.verify_ssl) != bool(kube_verify_ssl)
        or bool(connection.allow_weak_tls) != bool(kube_allow_weak_tls)
    )

    cluster.name = name
    cluster.environment = environment
    cluster.description = description

    parsed = parse_kubeconfig(kubeconfig) if kubeconfig else None

    if connection_changed:
        cluster.status = ClusterStatus.UNKNOWN.value
        connection.compatibility_status = 'validation_required'
        connection.compatibility_profile = None
        connection.readiness_status = 'validation_required'
        connection.lifecycle_status = None
        connection.discovery_summary = None
        connection.validation_message = (
            'Kubernetes connection credentials or TLS policy changed. Run Full Validation '
            'before KAORI treats this connection as ready.'
        )
        connection.last_validated_at = None
        cluster.last_check = None

    _sync_kubernetes_runtime(
        cluster,
        kubeconfig=kubeconfig,
        server=parsed['server'] if parsed else connection.server,
        verify_ssl=kube_verify_ssl,
        allow_weak_tls=kube_allow_weak_tls,
    )
    db.session.commit()

    return cluster


def delete_cluster(cluster: Cluster) -> dict[str, int]:
    """Delete a managed Kubernetes registration and its scope associations.

    Metrics Source and Alertmanager source instances are reusable and therefore are
    never deleted with the cluster. Only bindings that target this Kubernetes
    scope are removed. Generated reports and schedules are preserved by
    detaching their cluster reference before the cluster row is deleted.
    """
    cluster_id = str(cluster.id)
    connection = cluster.kubernetes_connection
    connection_id = connection.id if connection is not None else None
    acquire_resource_admission_locks(
        f'kubernetes-cluster:{cluster_id}',
        f'integration:kubernetes:{connection_id}' if connection_id is not None else None,
    )
    connection = cluster.kubernetes_connection
    canonical = connection.integration_instance if connection else None

    if connection is not None:
        guard = kubernetes_deletion_guard(
            connection_id=connection.id,
            cluster_id=cluster_id,
        )
        if guard.blocked:
            raise DeletionBlocked(guard)

    detached_reports = Report.query.filter(Report.cluster_id == cluster_id).update(
        {Report.cluster_id: None}, synchronize_session=False
    )
    detached_schedules = ReportSchedule.query.filter(ReportSchedule.cluster_id == cluster_id).update(
        {ReportSchedule.cluster_id: None}, synchronize_session=False
    )

    canonical_bindings = IntegrationBinding.query.filter(
        IntegrationBinding.asset_type == 'kubernetes_cluster',
        IntegrationBinding.asset_key == cluster_id,
    ).delete(synchronize_session=False)

    # The Cluster relationship removes KubernetesConnection and all rows that
    # carry a real cluster FK. Flush before deleting the canonical integration
    # identity so SQLAlchemy does not attempt to delete the connection twice.
    db.session.delete(cluster)
    db.session.flush()

    if canonical is not None:
        db.session.delete(canonical)

    db.session.commit()

    return {
        'canonical_bindings': int(canonical_bindings or 0),
        'detached_reports': int(detached_reports or 0),
        'detached_schedules': int(detached_schedules or 0),
        'canonical_instance_deleted': int(canonical is not None),
    }


def build_cluster_context(
    *,
    page: int | str | None = None,
    per_page: int | str | None = None,
    search: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    selected_page = normalize_page(
        page,
    )
    selected_per_page = normalize_per_page(
        per_page,
    )
    selected_search = normalize_search(
        search,
    )
    selected_environment = normalize_environment(
        environment,
    )

    clusters, inventory_summary, pagination = get_cluster_summary(
        page=selected_page,
        per_page=selected_per_page,
        search=selected_search,
        environment=selected_environment,
    )

    cluster_ids = [cluster.id for cluster in clusters]

    stats = get_cluster_stats()

    return {
        'clusters': clusters,
        'inventory_summary': inventory_summary,
        'metrics_source_summary': get_metrics_source_summary(
            clusters,
        ),
        'alertmanager_summary': get_alertmanager_summary(
            cluster_ids,
        ),
        'connected_clusters': stats['connected_clusters'],
        'synced_clusters': stats['synced_clusters'],
        'total_clusters': stats['total_clusters'],
        'pagination': pagination,
        'per_page_options': CLUSTER_PER_PAGE_OPTIONS,
        'selected_search': selected_search,
        'selected_environment': selected_environment,
        'selected_per_page': selected_per_page,
    }
