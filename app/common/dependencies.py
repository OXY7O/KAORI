from __future__ import annotations

from typing import Literal, Protocol, TypedDict

from flask import render_template, url_for

DependencyKind = Literal[
    'cluster_required',
    'metrics_source_setup',
    'metrics_source_connection',
    'metrics_source_capability',
    'alert_source_setup',
    'alert_source_connection',
]


class ClusterIdentity(Protocol):
    @property
    def id(self) -> object: ...

    @property
    def name(self) -> object: ...


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
        'badge': 'Cluster Required',
        'title': 'Kubernetes Cluster Required',
        'description': 'Add or select a Kubernetes cluster before loading worker-prepared analytics data.',
        'diagnostic_detail': None,
        'icon': 'server-cog',
        'action_label': 'Add Cluster',
        'action_url': url_for('cluster.add_cluster'),
        'permission': 'clusters.manage',
    }


def metrics_source_setup_blocker(cluster: ClusterIdentity) -> DependencyBlocker:
    return {
        'kind': 'metrics_source_setup',
        'stage': 2,
        'badge': 'Metrics Source Required',
        'title': 'Metrics Source Setup Required',
        'description': (
            f'No eligible metrics source is bound to {cluster.name}. Register and bind a metrics source so KAORI workers can prepare analytics snapshots.'
        ),
        'diagnostic_detail': None,
        'icon': 'activity',
        'action_label': 'Register Metrics Source',
        'action_url': url_for('integrations.select_metrics_source_provider'),
        'permission': 'settings.manage_integrations',
    }


def metrics_source_connection_blocker(
    cluster: ClusterIdentity,
    *,
    detail: str | None = None,
) -> DependencyBlocker:
    return {
        'kind': 'metrics_source_connection',
        'stage': 2,
        'badge': 'Metrics Source Unavailable',
        'title': 'Metrics Source Connection Unavailable',
        'description': (
            f'The selected metrics source is unreachable for {cluster.name}. Review the toast or Activity Log for technical details.'
        ),
        'diagnostic_detail': detail,
        'icon': 'plug-zap',
        'action_label': 'Review Metrics Sources',
        'action_url': url_for('integrations.metrics_sources'),
        'permission': 'settings.manage_integrations',
    }


def metrics_source_capability_blocker(
    cluster: ClusterIdentity,
    *,
    capability_labels: list[str] | None = None,
    feature_label: str = 'Storage Analytics',
    missing_capabilities: list[str] | None = None,
) -> DependencyBlocker:
    selected = capability_labels if capability_labels is not None else missing_capabilities
    labels = ', '.join(selected or []) if selected else 'required capabilities'
    return {
        'kind': 'metrics_source_capability',
        'stage': 2,
        'badge': f'{feature_label} Capability Incomplete',
        'title': f'{feature_label} Integration Contract Not Ready',
        'description': (
            f'{cluster.name} is connected, but {feature_label} requires additional '
            f'capabilities: {labels}. Resolve them at the bound metrics source before '
            'using this page.'
        ),
        'diagnostic_detail': None,
        'icon': 'shield-alert',
        'action_label': 'Review Capability',
        'action_url': url_for('integrations.metrics_sources'),
        'permission': 'settings.manage_integrations',
    }


def alert_source_setup_blocker(
    cluster: ClusterIdentity,
    *,
    source: str,
) -> DependencyBlocker:
    normalized_source = source.strip().lower()

    if normalized_source == 'metrics_source':
        return metrics_source_setup_blocker(cluster)

    if normalized_source == 'alertmanager':
        title = 'Alertmanager Setup Required'
        description = f'Alertmanager is not configured for {cluster.name}. Configure it to load alert routing and lifecycle context.'
        badge = 'Alertmanager Required'
        action_label = 'Add Alertmanager'
        action_url = url_for('alertmanager.new_instance', cluster_id=cluster.id)
    else:
        title = 'Alert Source Setup Required'
        description = f'No alert source is configured for {cluster.name}. Configure Alertmanager or a metrics source to load alert data.'
        badge = 'Alert Source Required'
        action_label = 'Add Alertmanager'
        action_url = url_for('alertmanager.new_instance', cluster_id=cluster.id)

    return {
        'kind': 'alert_source_setup',
        'stage': 3,
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
    cluster: ClusterIdentity,
    *,
    source: str,
    detail: str | None = None,
) -> DependencyBlocker:
    normalized_source = source.strip().lower()
    source_label = (
        'Alert source'
        if normalized_source in {'', 'auto', 'none'}
        else 'Metrics Source'
        if normalized_source == 'metrics_source'
        else normalized_source.title()
    )

    action_endpoint = (
        'integrations.metrics_sources' if normalized_source == 'metrics_source' else 'integrations.alertmanager'
    )

    return {
        'kind': 'alert_source_connection',
        'stage': 3,
        'badge': f'{source_label} Unavailable',
        'title': f'{source_label} Connection Unavailable',
        'description': (
            f'{source_label} is unreachable for {cluster.name}. Review the toast or Activity Log for technical details.'
        ),
        'diagnostic_detail': detail,
        'icon': 'triangle-alert',
        'action_label': 'Review Integration',
        'action_url': url_for(action_endpoint),
        'permission': 'settings.manage_integrations',
    }


def render_dependency_blocker(blocker: DependencyBlocker) -> str:
    """Render a compact KAORI Violet dependency state for Analytics partials."""
    return render_template(
        'components/dependencies/_blocker.html',
        dependency_blocker=blocker,
    )
