from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import url_for
from sqlalchemy import or_

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.inventory import (
    IngressInventory,
    NamespaceInventory,
    NodeInventory,
    PodInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem

MAX_RESULTS_PER_RESOURCE = 8
MAX_RESULTS_TOTAL = 24
MIN_RESOURCE_QUERY_LENGTH = 2


@dataclass(frozen=True)
class NavigationEntry:
    label: str
    description: str
    endpoint: str
    icon: str
    permission: str | None
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultDraft:
    result_id: str
    kind: str
    title: str
    subtitle: str
    url: str
    icon: str
    searchable: str
    status: object = None


NAVIGATION_ENTRIES: tuple[NavigationEntry, ...] = (
    NavigationEntry('Welcome', 'KAORI workspace overview', 'welcome.index', 'sparkles', None, ('home', 'start')),
    NavigationEntry(
        'Kubernetes Dashboard',
        'Operational Kubernetes summary',
        'kubernetes_dashboard.index',
        'layout-dashboard',
        'dashboard.view',
        ('dashboard', 'kubernetes'),
    ),
    NavigationEntry(
        'Kubernetes Inventory',
        'Committed Kubernetes resource inventory',
        'inventory.overview',
        'boxes',
        'inventory.view',
        ('inventory', 'resources'),
    ),
    NavigationEntry('Nodes', 'Kubernetes Inventory', 'inventory.nodes', 'server', 'inventory.view'),
    NavigationEntry('Namespaces', 'Kubernetes Inventory', 'inventory.namespaces', 'folders', 'inventory.view'),
    NavigationEntry('Workloads', 'Kubernetes Inventory', 'inventory.workloads', 'boxes', 'inventory.view'),
    NavigationEntry('Pods', 'Kubernetes Inventory', 'inventory.pods', 'box', 'inventory.view'),
    NavigationEntry('Services', 'Kubernetes Inventory', 'inventory.services', 'network', 'inventory.view'),
    NavigationEntry('Ingresses', 'Kubernetes Inventory', 'inventory.ingresses', 'route', 'inventory.view'),
    NavigationEntry('Storage', 'Kubernetes Inventory', 'inventory.storage', 'hard-drive', 'inventory.view'),
    NavigationEntry(
        'Object Storage Inventory',
        'Managed object-storage inventory',
        'object_storage_inventory.overview',
        'database',
        'object_storage_inventory.view',
        ('object storage', 'inventory'),
    ),
    NavigationEntry(
        'Object Storage Systems',
        'Managed storage systems',
        'object_storage_inventory.systems',
        'server',
        'object_storage_inventory.view',
        ('object storage', 'systems'),
    ),
    NavigationEntry(
        'Buckets & Containers',
        'Object-storage namespaces',
        'object_storage_inventory.buckets',
        'container',
        'object_storage_inventory.view',
        ('bucket', 'container', 'object storage'),
    ),
    NavigationEntry(
        'Kubernetes Analytics',
        'Kubernetes operational analytics',
        'analytics.overview',
        'chart-no-axes-combined',
        'analytics.view',
        ('analytics', 'kubernetes'),
    ),
    NavigationEntry('Capacity', 'Kubernetes Analytics', 'analytics.capacity', 'gauge', 'analytics.view'),
    NavigationEntry('Forecast', 'Kubernetes Analytics', 'analytics.forecast', 'line-chart', 'analytics.view'),
    NavigationEntry(
        'Alerts & Anomalies',
        'Kubernetes Analytics',
        'analytics.alerts',
        'triangle-alert',
        'analytics.view',
        ('alerts', 'anomalies'),
    ),
    NavigationEntry(
        'Object Storage Analytics',
        'Object-storage operational analytics',
        'analytics.object_storage_overview',
        'chart-no-axes-combined',
        'object_storage_analytics.view',
        ('object storage', 'analytics'),
    ),
    NavigationEntry(
        'Alert Intelligence',
        'Investigate active alert operations',
        'alert_intelligence.index',
        'triangle-alert',
        'intelligence.view',
        ('alert center', 'intelligence'),
    ),
    NavigationEntry(
        'Recommendations',
        'Operational recommendations',
        'intelligence.recommendations',
        'sparkles',
        'intelligence.view',
    ),
    NavigationEntry('Rule Catalog', 'Intelligence', 'intelligence.catalog', 'list-checks', 'intelligence.view'),
    NavigationEntry('Reports', 'Generated and scheduled reports', 'reports.overview', 'file-bar-chart', 'reports.view'),
)

QUICK_NAV_ENDPOINTS = {
    'welcome.index',
    'kubernetes_dashboard.index',
    'inventory.overview',
    'object_storage_inventory.overview',
    'analytics.overview',
    'analytics.object_storage_overview',
    'alert_intelligence.index',
    'reports.overview',
}


def _normalize(value: object) -> str:
    return str(value or '').strip().lower()


def _score(query: str, title: str, searchable: str, *, current_scope: bool = False) -> int:
    q = _normalize(query)
    title_value = _normalize(title)
    searchable_value = _normalize(searchable)
    if not q:
        return 0
    if title_value == q:
        score = 120
    elif title_value.startswith(q):
        score = 90
    elif q in title_value:
        score = 70
    elif q in searchable_value:
        score = 45
    else:
        return 0
    if current_scope:
        score += 20
    return score


def _status_tone(status: object) -> str:
    value = _normalize(status)
    if value in {'running', 'ready', 'connected', 'healthy', 'active', 'bound', 'normal'}:
        return 'normal'
    if value in {'warning', 'pending', 'degraded', 'unknown'}:
        return 'warning' if value != 'unknown' else 'unknown'
    if value in {'failed', 'critical', 'error', 'offline', 'lost'}:
        return 'critical'
    return 'unknown'


def _result(draft: ResultDraft, *, query: str, current_scope: bool = False) -> dict[str, Any] | None:
    score = _score(query, draft.title, draft.searchable, current_scope=current_scope)
    if score <= 0:
        return None
    status_value = str(draft.status or '').strip()
    return {
        'id': draft.result_id,
        'kind': draft.kind,
        'title': draft.title,
        'subtitle': draft.subtitle,
        'url': draft.url,
        'icon': draft.icon,
        'status': status_value,
        'status_tone': _status_tone(status_value) if status_value else '',
        '_score': score,
    }


def navigation_results(*, query: str, has_permission: Callable[[str], bool]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for entry in NAVIGATION_ENTRIES:
        if entry.permission and not has_permission(entry.permission):
            continue
        if not query and entry.endpoint not in QUICK_NAV_ENDPOINTS:
            continue
        searchable = ' '.join((entry.label, entry.description, *entry.keywords))
        score = _score(query, entry.label, searchable) if query else 1
        if query and score <= 0:
            continue
        entries.append(
            {
                'id': f'navigation:{entry.endpoint}',
                'kind': 'Navigation',
                'title': entry.label,
                'subtitle': entry.description,
                'url': url_for(entry.endpoint),
                'icon': entry.icon,
                'status': '',
                'status_tone': '',
                '_score': score,
            }
        )
    if query:
        entries.sort(key=lambda item: (-int(item['_score']), str(item['title']).lower()))
    return entries[:8]


def _kubernetes_resource_results(query: str, current_cluster_id: str) -> list[dict[str, Any]]:
    like = f'%{query}%'
    results: list[dict[str, Any]] = []

    clusters = (
        db.session.query(Cluster)
        .filter(or_(Cluster.name.ilike(like), Cluster.environment.ilike(like)))
        .limit(MAX_RESULTS_PER_RESOURCE)
        .all()
    )
    for cluster in clusters:
        item = _result(
            ResultDraft(
                result_id=f'cluster:{cluster.id}',
                kind='Cluster',
                title=cluster.name,
                subtitle=f'Cluster · {cluster.environment}',
                url=url_for('inventory.overview', detail=cluster.id),
                icon='boxes',
                searchable=f'{cluster.name} {cluster.environment}',
                status=cluster.status,
            ),
            query=query,
            current_scope=str(cluster.id) == current_cluster_id,
        )
        if item:
            results.append(item)

    specs = (
        (
            NodeInventory,
            NodeInventory.node_name,
            'Node',
            'server',
            'inventory.nodes',
            lambda row: '',
            lambda row: row.status,
        ),
        (
            NamespaceInventory,
            NamespaceInventory.namespace,
            'Namespace',
            'folders',
            'inventory.namespaces',
            lambda row: '',
            lambda row: row.status,
        ),
        (
            WorkloadInventory,
            WorkloadInventory.name,
            'Workload',
            'boxes',
            'inventory.workloads',
            lambda row: row.namespace,
            lambda row: row.status,
        ),
        (
            PodInventory,
            PodInventory.pod_name,
            'Pod',
            'box',
            'inventory.pods',
            lambda row: row.namespace,
            lambda row: row.phase,
        ),
        (
            ServiceInventory,
            ServiceInventory.service_name,
            'Service',
            'network',
            'inventory.services',
            lambda row: row.namespace,
            lambda row: '',
        ),
        (
            IngressInventory,
            IngressInventory.ingress_name,
            'Ingress',
            'route',
            'inventory.ingresses',
            lambda row: row.namespace,
            lambda row: '',
        ),
        (
            StorageInventory,
            StorageInventory.name,
            'Storage',
            'hard-drive',
            'inventory.storage',
            lambda row: row.namespace or '',
            lambda row: row.status,
        ),
    )
    for model, name_column, kind, icon, endpoint, namespace_getter, status_getter in specs:
        rows = (
            db.session.query(model, Cluster.name)
            .join(Cluster, model.cluster_id == Cluster.id)
            .filter(name_column.ilike(like))
            .limit(MAX_RESULTS_PER_RESOURCE)
            .all()
        )
        for row, cluster_name in rows:
            title = str(getattr(row, name_column.key))
            namespace = str(namespace_getter(row) or '').strip()
            subtitle_parts = [kind]
            if namespace:
                subtitle_parts.append(namespace)
            subtitle_parts.append(str(cluster_name))
            item = _result(
                ResultDraft(
                    result_id=f'{kind.lower()}:{row.id}',
                    kind=kind,
                    title=title,
                    subtitle=' · '.join(subtitle_parts),
                    url=url_for(
                        endpoint,
                        cluster_id=row.cluster_id,
                        search=title,
                        detail=row.id,
                    ),
                    icon=icon,
                    searchable=f'{title} {namespace} {cluster_name}',
                    status=status_getter(row),
                ),
                query=query,
                current_scope=str(row.cluster_id) == current_cluster_id,
            )
            if item:
                results.append(item)

    return results


def _object_storage_resource_results(query: str) -> list[dict[str, Any]]:
    like = f'%{query}%'
    results: list[dict[str, Any]] = []
    systems = (
        db.session.query(ObjectStorageSystem)
        .filter(or_(ObjectStorageSystem.name.ilike(like), ObjectStorageSystem.environment.ilike(like)))
        .limit(MAX_RESULTS_PER_RESOURCE)
        .all()
    )
    for system in systems:
        item = _result(
            ResultDraft(
                result_id=f'object-storage-system:{system.id}',
                kind='Object Storage System',
                title=system.name,
                subtitle=f'Object Storage System · {system.environment}',
                url=url_for('object_storage_inventory.systems', search=system.name, detail=system.id),
                icon='server',
                searchable=f'{system.name} {system.environment}',
                status=system.status,
            ),
            query=query,
        )
        if item:
            results.append(item)

    buckets = (
        db.session.query(ObjectStorageBucket, ObjectStorageSystem.name)
        .join(ObjectStorageSystem, ObjectStorageBucket.object_storage_system_id == ObjectStorageSystem.id)
        .filter(ObjectStorageBucket.name.ilike(like))
        .limit(MAX_RESULTS_PER_RESOURCE)
        .all()
    )
    for bucket, system_name in buckets:
        item = _result(
            ResultDraft(
                result_id=f'object-storage-bucket:{bucket.id}',
                kind='Bucket / Container',
                title=bucket.name,
                subtitle=f'{bucket.native_type.title()} · {system_name}',
                url=url_for(
                    'object_storage_inventory.buckets',
                    system_id=bucket.object_storage_system_id,
                    search=bucket.name,
                    detail=bucket.id,
                ),
                icon='container',
                searchable=f'{bucket.name} {bucket.native_type} {system_name}',
                status=bucket.usage_stats_state,
            ),
            query=query,
        )
        if item:
            results.append(item)
    return results


def resource_results(
    *,
    query: str,
    current_cluster_id: str,
    can_view_kubernetes_inventory: bool,
    can_view_object_storage_inventory: bool,
) -> list[dict[str, Any]]:
    if len(query.strip()) < MIN_RESOURCE_QUERY_LENGTH:
        return []
    results: list[dict[str, Any]] = []
    if can_view_kubernetes_inventory:
        results.extend(_kubernetes_resource_results(query, current_cluster_id))
    if can_view_object_storage_inventory:
        results.extend(_object_storage_resource_results(query))
    results.sort(key=lambda item: (-int(item['_score']), str(item['title']).lower(), str(item['kind']).lower()))
    return results[:MAX_RESULTS_TOTAL]


def strip_internal_score(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if key != '_score'} for item in items]
