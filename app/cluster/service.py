from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any

import yaml
from sqlalchemy import func, or_

from app.extensions import db
from app.integrations.kubernetes import kubeconfig_for_cluster
from app.integrations.deletion import DeletionBlocked, kubernetes_deletion_guard
from app.alertmanager.resolver import resolve_alertmanager_sources
from app.prometheus.repository import resolve_instance_for_cluster
from app.kubernetes.service import test_cluster_connection, test_cluster_runtime_health
from app.models import (
    AlertmanagerBinding,
    AlertmanagerInstance,
    Cluster,
    ClusterInventory,
    ClusterStatus,
    NamespaceInventory,
    PrometheusBinding,
    Report,
    ReportSchedule,
)
from app.models.integration import IntegrationBinding, IntegrationInstance, KubernetesConnection

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
    query = Cluster.query

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
                Cluster.server.ilike(
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

        inventory_summary[cluster.id] = {
            'version': cluster.kubernetes_version or (inventory.kubernetes_version if inventory else '-'),
            'compatibility_status': cluster.kubernetes_compatibility_status or 'not_checked',
            'readiness_status': cluster.kubernetes_readiness_status or 'not_checked',
            'lifecycle_status': cluster.kubernetes_lifecycle_status or 'unknown',
            'api_profile': cluster.kubernetes_compatibility_profile or 'not_checked',
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


def get_prometheus_summary(
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



def _sync_kubernetes_runtime(cluster: Cluster, *, kubeconfig: str | None = None) -> KubernetesConnection:
    connection = cluster.kubernetes_connection
    canonical = connection.integration_instance if connection else None
    if canonical is None:
        canonical = IntegrationInstance(
            provider_type='kubernetes',
            name=f'{cluster.name} Kubernetes API',
            description=cluster.description,
            environment=cluster.environment,
            enabled=True,
            readiness_status=cluster.kubernetes_readiness_status,
            health_status=cluster.status,
            last_checked_at=cluster.last_check,
            metadata_json={'asset_type': 'kubernetes_cluster', 'asset_key': cluster.id},
        )
        db.session.add(canonical)
        db.session.flush()
    else:
        canonical.name = f'{cluster.name} Kubernetes API'
        canonical.description = cluster.description
        canonical.environment = cluster.environment
        canonical.readiness_status = cluster.kubernetes_readiness_status
        canonical.health_status = cluster.status
        canonical.last_checked_at = cluster.last_check

    if connection is None:
        connection = KubernetesConnection(
            integration_instance_id=canonical.id,
            cluster_id=cluster.id,
            kubeconfig=kubeconfig or '',
        )
        db.session.add(connection)
    connection.kubeconfig = kubeconfig or connection.kubeconfig
    connection.verify_ssl = cluster.kube_verify_ssl
    connection.allow_weak_tls = cluster.kube_allow_weak_tls
    connection.server = cluster.server
    connection.compatibility_profile = cluster.kubernetes_compatibility_profile
    connection.readiness_status = cluster.kubernetes_readiness_status
    connection.validation_message = cluster.kubernetes_validation_message
    connection.last_validated_at = cluster.kubernetes_last_validated_at
    connection.discovery_summary = cluster.kubernetes_api_discovery_summary

    binding = IntegrationBinding.query.filter_by(
        integration_instance_id=canonical.id,
        asset_type='kubernetes_cluster',
        asset_key=cluster.id,
        binding_role='primary',
    ).first()
    if binding is None:
        db.session.add(IntegrationBinding(
            integration_instance_id=canonical.id,
            asset_type='kubernetes_cluster',
            asset_key=cluster.id,
            binding_role='primary',
            priority=100,
            enabled=True,
            capability_scope=['inventory', 'operations', 'governance', 'discovery'],
        ))
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
    cluster.kubeconfig = kubeconfig
    cluster.server = result['server']
    cluster.kube_verify_ssl = kube_verify_ssl
    cluster.kube_allow_weak_tls = kube_allow_weak_tls

    db.session.add(
        cluster,
    )
    db.session.flush()
    _sync_kubernetes_runtime(cluster, kubeconfig=kubeconfig)
    db.session.commit()

    return cluster



def refresh_cluster_runtime_health(cluster: Cluster) -> dict[str, Any]:
    """Refresh lightweight API health without rebuilding capability evidence."""
    result = test_cluster_runtime_health(
        kubeconfig_content=kubeconfig_for_cluster(cluster),
        endpoint=cluster.server,
        verify_ssl=bool(getattr(cluster, 'kube_verify_ssl', True)),
        allow_weak_tls=bool(getattr(cluster, 'kube_allow_weak_tls', False)),
    )
    cluster.last_check = datetime.now(UTC)
    if result['success']:
        cluster.status = ClusterStatus.CONNECTED.value
        cluster.kubernetes_version = result.get('version') or cluster.kubernetes_version
        cluster.kubernetes_platform = result.get('platform') or cluster.kubernetes_platform
    else:
        cluster.status = ClusterStatus.FAILED.value

    # Preserve compatibility, readiness, API discovery, and capability evidence.
    _sync_kubernetes_runtime(cluster)
    db.session.commit()
    return result

def run_test_cluster(cluster: Cluster) -> dict[str, Any]:
    verify_ssl = bool(
        getattr(
            cluster,
            'kube_verify_ssl',
            True,
        )
    )

    allow_weak_tls = bool(
        getattr(
            cluster,
            'kube_allow_weak_tls',
            False,
        )
    )

    result = test_cluster_connection(
        kubeconfig_content=kubeconfig_for_cluster(cluster),
        endpoint=cluster.server,
        verify_ssl=verify_ssl,
        allow_weak_tls=allow_weak_tls,
    )

    cluster.last_check = datetime.now(
        UTC,
    )

    if result['success']:
        cluster.status = ClusterStatus.CONNECTED.value

        cluster.node_count = result.get('node_count', 0)
        cluster.kubernetes_version = result.get('version')
        cluster.kubernetes_platform = result.get('platform')
        cluster.kubernetes_compatibility_status = result.get('compatibility_status')
        cluster.kubernetes_compatibility_profile = result.get('compatibility_profile')
        cluster.kubernetes_readiness_status = result.get('readiness_status')
        cluster.kubernetes_lifecycle_status = result.get('lifecycle_status')
        cluster.kubernetes_api_discovery_summary = result.get('api_discovery_summary')
        cluster.kubernetes_validation_message = result.get('validation_message')
        cluster.kubernetes_last_validated_at = datetime.now(UTC)

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

    connection_changed = bool(kubeconfig) or (
        bool(cluster.kube_verify_ssl) != bool(kube_verify_ssl)
        or bool(cluster.kube_allow_weak_tls) != bool(kube_allow_weak_tls)
    )

    cluster.name = name
    cluster.environment = environment
    cluster.description = description
    cluster.kube_verify_ssl = kube_verify_ssl
    cluster.kube_allow_weak_tls = kube_allow_weak_tls

    if kubeconfig:
        parsed = parse_kubeconfig(kubeconfig)
        cluster.kubeconfig = kubeconfig
        cluster.server = parsed['server']

    if connection_changed:
        cluster.status = ClusterStatus.UNKNOWN.value
        cluster.kubernetes_compatibility_status = 'validation_required'
        cluster.kubernetes_compatibility_profile = None
        cluster.kubernetes_readiness_status = 'validation_required'
        cluster.kubernetes_lifecycle_status = None
        cluster.kubernetes_api_discovery_summary = None
        cluster.kubernetes_validation_message = (
            'Kubernetes connection credentials or TLS policy changed. Run Full Validation '
            'before KAORI treats this connection as ready.'
        )
        cluster.kubernetes_last_validated_at = None
        cluster.last_check = None

    _sync_kubernetes_runtime(cluster, kubeconfig=kubeconfig)
    db.session.commit()

    return cluster


def delete_cluster(cluster: Cluster) -> dict[str, int]:
    """Delete a managed Kubernetes registration and its scope associations.

    Prometheus and Alertmanager source instances are reusable and therefore are
    never deleted with the cluster. Only bindings that target this Kubernetes
    scope are removed. Generated reports and schedules are preserved by
    detaching their cluster reference before the cluster row is deleted.
    """
    cluster_id = str(cluster.id)
    connection = cluster.kubernetes_connection
    canonical = connection.integration_instance if connection else None

    if connection is not None:
        guard = kubernetes_deletion_guard(
            connection_id=connection.id,
            cluster_id=cluster_id,
        )
        if guard.blocked:
            raise DeletionBlocked(guard)

    detached_reports = (
        Report.query.filter(Report.cluster_id == cluster_id)
        .update({Report.cluster_id: None}, synchronize_session=False)
    )
    detached_schedules = (
        ReportSchedule.query.filter(ReportSchedule.cluster_id == cluster_id)
        .update({ReportSchedule.cluster_id: None}, synchronize_session=False)
    )

    canonical_bindings = (
        IntegrationBinding.query.filter(
            IntegrationBinding.asset_type == 'kubernetes_cluster',
            IntegrationBinding.asset_key == cluster_id,
        )
        .delete(synchronize_session=False)
    )
    legacy_prometheus_bindings = (
        PrometheusBinding.query.filter(
            PrometheusBinding.scope_type == 'kubernetes_cluster',
            PrometheusBinding.scope_key == cluster_id,
        )
        .delete(synchronize_session=False)
    )
    legacy_alertmanager_bindings = (
        AlertmanagerBinding.query.filter(
            AlertmanagerBinding.scope_type == 'kubernetes_cluster',
            AlertmanagerBinding.scope_key == cluster_id,
        )
        .delete(synchronize_session=False)
    )

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
        'legacy_prometheus_bindings': int(legacy_prometheus_bindings or 0),
        'legacy_alertmanager_bindings': int(legacy_alertmanager_bindings or 0),
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
        'prometheus_summary': get_prometheus_summary(
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
