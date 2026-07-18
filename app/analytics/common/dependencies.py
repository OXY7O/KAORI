from __future__ import annotations

from dataclasses import dataclass

from app.alertmanager.resolver import resolve_alertmanager_sources
from app.models import Cluster
from app.prometheus.repository import resolve_instance_for_cluster


@dataclass(frozen=True, slots=True)
class ClusterDependencyState:
    cluster_id: str
    cluster_name: str
    kubernetes_ready: bool
    prometheus_ready: bool
    alertmanager_ready: bool
    prometheus_reason: str | None = None
    alertmanager_reason: str | None = None

    def allows(self, *, require_prometheus: bool = True, require_alertmanager: bool = False) -> bool:
        return (
            self.kubernetes_ready
            and (self.prometheus_ready or not require_prometheus)
            and (self.alertmanager_ready or not require_alertmanager)
        )


def dependency_state_for_cluster(cluster: Cluster) -> ClusterDependencyState:
    prometheus = resolve_instance_for_cluster(cluster.id)
    prom_ready = bool(
        prometheus
        and prometheus.enabled
        and prometheus.endpoint
        and prometheus.readiness_status == 'ready'
        and prometheus.last_status == 'connected'
    )
    if prometheus is None:
        prom_reason = 'No standalone Prometheus runtime is bound to this cluster.'
    elif not prometheus.endpoint:
        prom_reason = 'The bound Prometheus runtime has no endpoint.'
    elif prometheus.readiness_status != 'ready':
        prom_reason = prometheus.validation_message or 'The bound Prometheus runtime is not ready.'
    elif prometheus.last_status != 'connected':
        prom_reason = prometheus.last_error or 'The bound Prometheus runtime is not connected.'
    else:
        prom_reason = None

    resolution = resolve_alertmanager_sources(
        scope_type='kubernetes_cluster',
        scope_key=cluster.id,
        required_capabilities=(),
    )
    selected_source = resolution.selected
    alertmanager = selected_source.instance if selected_source else None
    alert_ready = bool(
        alertmanager
        and alertmanager.enabled
        and alertmanager.endpoint
        and alertmanager.readiness_status == 'ready'
        and alertmanager.last_status == 'connected'
    )
    if alertmanager is None:
        alert_reason = 'No standalone Alertmanager runtime is bound to this cluster.'
    elif alertmanager.readiness_status != 'ready':
        alert_reason = alertmanager.validation_message or 'The bound Alertmanager runtime is not ready.'
    elif alertmanager.last_status != 'connected':
        alert_reason = alertmanager.last_error or 'The bound Alertmanager runtime is not connected.'
    else:
        alert_reason = None

    kubernetes_ready = cluster.status == 'connected'
    return ClusterDependencyState(
        cluster_id=cluster.id,
        cluster_name=cluster.name,
        kubernetes_ready=kubernetes_ready,
        prometheus_ready=prom_ready,
        alertmanager_ready=alert_ready,
        prometheus_reason=prom_reason,
        alertmanager_reason=alert_reason,
    )
