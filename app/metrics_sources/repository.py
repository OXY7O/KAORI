from __future__ import annotations

from app.integrations.observability.metrics_source.scope import (
    KUBERNETES_CLUSTER_SCOPE,
    cluster_bindings_for_instance,
    primary_cluster_id_for_instance,
)
from app.models.metrics_source import MetricsSource

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
) -> MetricsSource | None:
    from app.metrics_sources.resolver import resolve_metrics_sources

    resolution = resolve_metrics_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=cluster_id,
        required_binding_capabilities=required_capabilities,
    )
    selected = resolution.selected
    return selected.instance if selected is not None else None


def get_instance(instance_id: int) -> MetricsSource | None:
    return MetricsSource.query.filter_by(id=instance_id).first()


def list_instances() -> list[MetricsSource]:
    return MetricsSource.query.order_by(
        MetricsSource.created_at.asc(),
        MetricsSource.id.asc(),
    ).all()
