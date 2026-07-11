from __future__ import annotations

from typing import Literal, TypedDict

from flask import url_for

from app.models.cluster import Cluster

DependencyKind = Literal[
    'cluster_required',
    'prometheus_setup',
    'prometheus_connection',
    'alert_source_setup',
    'alert_source_connection',
]


class DependencyBlocker(TypedDict):
    kind: DependencyKind
    stage: int
    badge: str
    title: str
    description: str
    icon: str
    action_label: str | None
    action_url: str | None
    permission: str | None


def cluster_required_blocker() -> DependencyBlocker:
    return {
        'kind': 'cluster_required',
        'stage': 1,
        'badge': 'Cluster required',
        'title': 'Add a Kubernetes cluster first',
        'description': (
            'This page needs a Kubernetes cluster before KAORI can evaluate integrations or load operational data.'
        ),
        'icon': 'server-cog',
        'action_label': 'Add first cluster',
        'action_url': url_for('cluster.add_cluster'),
        'permission': 'clusters.manage',
    }


def prometheus_setup_blocker(cluster: Cluster) -> DependencyBlocker:
    return {
        'kind': 'prometheus_setup',
        'stage': 2,
        'badge': 'Prometheus required',
        'title': 'Configure Prometheus for this cluster',
        'description': (
            f'Cluster {cluster.name} is available. Configure its Prometheus endpoint before loading live analytics.'
        ),
        'icon': 'activity',
        'action_label': 'Configure Prometheus',
        'action_url': url_for('prometheus.configuration', cluster_id=cluster.id),
        'permission': 'settings.manage_integrations',
    }


def prometheus_connection_blocker(
    cluster: Cluster,
    *,
    detail: str | None = None,
) -> DependencyBlocker:
    description = (
        f'Prometheus is configured for {cluster.name}, but KAORI could not retrieve live metrics. '
        'Review endpoint reachability, credentials, TLS settings, and network access.'
    )

    if detail:
        description = f'{description} Detail: {detail}'

    return {
        'kind': 'prometheus_connection',
        'stage': 3,
        'badge': 'Prometheus unavailable',
        'title': 'Restore the Prometheus connection',
        'description': description,
        'icon': 'plug-zap',
        'action_label': 'Review Prometheus',
        'action_url': url_for('prometheus.configuration', cluster_id=cluster.id),
        'permission': 'settings.manage_integrations',
    }


def alert_source_setup_blocker(
    cluster: Cluster,
    *,
    source: str,
) -> DependencyBlocker:
    normalized_source = source.strip().lower()

    if normalized_source == 'prometheus':
        return prometheus_setup_blocker(cluster)

    if normalized_source == 'alertmanager':
        title = 'Configure Alertmanager for this cluster'
        description = (
            f'Cluster {cluster.name} is available. Configure Alertmanager before loading routing, grouping, silence, '
            'and inhibition context.'
        )
        action_label = 'Configure Alertmanager'
        action_url = url_for(
            'alertmanager.cluster_alertmanager_config',
            cluster_id=cluster.id,
        )
    else:
        title = 'Configure an alert source'
        description = f'Cluster {cluster.name} is available, but neither Alertmanager nor Prometheus is ready to provide alert data.'
        action_label = 'Configure Alertmanager'
        action_url = url_for(
            'alertmanager.cluster_alertmanager_config',
            cluster_id=cluster.id,
        )

    return {
        'kind': 'alert_source_setup',
        'stage': 2,
        'badge': 'Alert source required',
        'title': title,
        'description': description,
        'icon': 'bell-ring',
        'action_label': action_label,
        'action_url': action_url,
        'permission': 'settings.manage_integrations',
    }


def alert_source_connection_blocker(
    cluster: Cluster,
    *,
    source: str,
    detail: str | None = None,
) -> DependencyBlocker:
    source_label = source.strip().lower()
    source_label = 'Alert source' if source_label in {'', 'auto', 'none'} else source_label.title()

    description = (
        f'{source_label} is configured for {cluster.name}, but no usable alert connection is currently available.'
    )

    if detail:
        description = f'{description} Detail: {detail}'

    action_endpoint = (
        'prometheus.configuration'
        if source.strip().lower() == 'prometheus'
        else 'alertmanager.cluster_alertmanager_config'
    )

    return {
        'kind': 'alert_source_connection',
        'stage': 3,
        'badge': 'Alert source unavailable',
        'title': 'Restore the alert source connection',
        'description': description,
        'icon': 'triangle-alert',
        'action_label': 'Review integration',
        'action_url': url_for(action_endpoint, cluster_id=cluster.id),
        'permission': 'settings.manage_integrations',
    }
