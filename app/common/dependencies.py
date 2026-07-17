from __future__ import annotations

from typing import Literal, TypedDict

from flask import render_template, url_for

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
    diagnostic_detail: str | None
    icon: str
    action_label: str | None
    action_url: str | None
    permission: str | None


def cluster_required_blocker() -> DependencyBlocker:
    return {
        'kind': 'cluster_required',
        'stage': 1,
        'badge': 'Cluster required',
        'title': 'Kubernetes cluster required',
        'description': 'Add or select a Kubernetes cluster before loading analytics data.',
        'diagnostic_detail': None,
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
        'title': 'Prometheus setup required',
        'description': (
            f'Prometheus is not configured for {cluster.name}. Configure the integration to load live analytics.'
        ),
        'diagnostic_detail': None,
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
    return {
        'kind': 'prometheus_connection',
        'stage': 3,
        'badge': 'Prometheus unavailable',
        'title': 'Prometheus connection unavailable',
        'description': (
            f'Prometheus is unreachable for {cluster.name}. Review the toast or Activity Log for technical details.'
        ),
        'diagnostic_detail': detail,
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
        title = 'Alertmanager setup required'
        description = (
            f'Alertmanager is not configured for {cluster.name}. Configure it to load alert routing and lifecycle context.'
        )
        badge = 'Alertmanager required'
        action_label = 'Configure Alertmanager'
        action_url = url_for(
            'alertmanager.cluster_alertmanager_config',
            cluster_id=cluster.id,
        )
    else:
        title = 'Alert source setup required'
        description = (
            f'No alert source is configured for {cluster.name}. Configure Alertmanager or Prometheus to load alert data.'
        )
        badge = 'Alert source required'
        action_label = 'Configure Alertmanager'
        action_url = url_for(
            'alertmanager.cluster_alertmanager_config',
            cluster_id=cluster.id,
        )

    return {
        'kind': 'alert_source_setup',
        'stage': 2,
        'badge': badge,
        'title': title,
        'description': description,
        'diagnostic_detail': None,
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
    normalized_source = source.strip().lower()
    source_label = 'Alert source' if normalized_source in {'', 'auto', 'none'} else normalized_source.title()

    action_endpoint = (
        'prometheus.configuration'
        if normalized_source == 'prometheus'
        else 'alertmanager.cluster_alertmanager_config'
    )

    return {
        'kind': 'alert_source_connection',
        'stage': 3,
        'badge': f'{source_label} unavailable',
        'title': f'{source_label} connection unavailable',
        'description': (
            f'{source_label} is unreachable for {cluster.name}. Review the toast or Activity Log for technical details.'
        ),
        'diagnostic_detail': detail,
        'icon': 'triangle-alert',
        'action_label': 'Review integration',
        'action_url': url_for(action_endpoint, cluster_id=cluster.id),
        'permission': 'settings.manage_integrations',
    }


def render_dependency_blocker(blocker: DependencyBlocker) -> str:
    """Render a compact KAORI Violet dependency state for Analytics partials."""
    return render_template(
        'components/dependencies/_blocker.html',
        dependency_blocker=blocker,
    )
