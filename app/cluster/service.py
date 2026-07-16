from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any

import yaml
from sqlalchemy import func, or_

from app.extensions import db
from app.kubernetes.service import test_cluster_connection
from app.models import (
    AlertmanagerConfig,
    Cluster,
    ClusterInventory,
    ClusterStatus,
    NamespaceInventory,
)

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

    if not cluster_ids:
        return summary

    configs = AlertmanagerConfig.query.filter(
        AlertmanagerConfig.cluster_id.in_(
            cluster_ids,
        )
    ).all()

    for config in configs:
        summary[config.cluster_id] = {
            'configured': bool(
                config.endpoint,
            ),
            'connected': config.last_status == 'connected',
            'status': config.last_status or 'configured',
            'label': config.display_status,
            'response_time_ms': config.last_response_time_ms,
            'last_checked_at': config.last_checked_at,
            'error': config.last_error,
        }

    return summary


def get_prometheus_summary(
    clusters: list[Cluster],
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}

    for cluster in clusters:
        config = getattr(
            cluster,
            'prometheus_config',
            None,
        )

        if config is None:
            summary[cluster.id] = {
                'configured': False,
                'label': 'Not Set',
                'endpoint': None,
            }
            continue

        endpoint = getattr(
            config,
            'endpoint',
            None,
        )

        summary[cluster.id] = {
            'configured': bool(
                endpoint,
            ),
            'label': 'Configured' if endpoint else 'Not Set',
            'endpoint': endpoint,
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
    db.session.commit()

    return cluster


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
        kubeconfig_content=cluster.kubeconfig,
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
        cluster.kubernetes_validation_message = result.get('validation_message')
        cluster.kubernetes_last_validated_at = datetime.now(UTC)

    else:
        cluster.status = ClusterStatus.FAILED.value

    db.session.commit()

    return result


def update_cluster(
    *,
    cluster: Cluster,
    name: str,
    environment: str,
    description: str | None,
    kube_verify_ssl: bool = True,
    kube_allow_weak_tls: bool = False,
) -> Cluster:
    existing = Cluster.query.filter(
        Cluster.name == name,
        Cluster.id != cluster.id,
    ).first()

    if existing:
        raise ValueError('Cluster name already exists')

    cluster.name = name
    cluster.environment = environment
    cluster.description = description
    cluster.kube_verify_ssl = kube_verify_ssl
    cluster.kube_allow_weak_tls = kube_allow_weak_tls

    db.session.commit()

    return cluster


def delete_cluster(cluster: Cluster) -> None:
    db.session.delete(
        cluster,
    )

    db.session.commit()


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
