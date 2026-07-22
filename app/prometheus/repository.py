from __future__ import annotations

from app.integrations.prometheus.scope import (
    KUBERNETES_CLUSTER_SCOPE,
    cluster_bindings_for_instance,
    primary_cluster_id_for_instance,
)
from app.models.prometheus import PrometheusInstance

__all__ = [
    'KUBERNETES_CLUSTER_SCOPE',
    'cluster_bindings_for_instance',
    'primary_cluster_id_for_instance',
    'resolve_instance_for_cluster',
    'get_instance',
    'list_instances',
]


def resolve_instance_for_cluster(
    cluster_id: str,
    *,
    required_capabilities: tuple[str, ...] = (),
) -> PrometheusInstance | None:
    from app.prometheus.resolver import resolve_prometheus_sources

    resolution = resolve_prometheus_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=cluster_id,
        required_binding_capabilities=required_capabilities,
    )
    selected = resolution.selected
    return selected.instance if selected is not None else None


def get_instance(instance_id: int) -> PrometheusInstance | None:
    return PrometheusInstance.query.filter_by(id=instance_id).first()


def list_instances() -> list[PrometheusInstance]:
    return PrometheusInstance.query.order_by(
        PrometheusInstance.created_at.asc(),
        PrometheusInstance.id.asc(),
    ).all()
