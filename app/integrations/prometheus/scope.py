from __future__ import annotations

from app.models.integration import IntegrationBinding
from app.models.prometheus import PrometheusInstance

KUBERNETES_CLUSTER_SCOPE = 'kubernetes_cluster'


def cluster_bindings_for_instance(
    instance: PrometheusInstance,
    *,
    enabled_only: bool = False,
) -> list[IntegrationBinding]:
    """Return canonical managed-cluster bindings for one Prometheus source."""
    if instance.integration_instance_id is None:
        return []
    query = IntegrationBinding.query.filter_by(
        integration_instance_id=instance.integration_instance_id,
        asset_type=KUBERNETES_CLUSTER_SCOPE,
    )
    if enabled_only:
        query = query.filter_by(enabled=True)
    return query.order_by(
        IntegrationBinding.priority.asc(),
        IntegrationBinding.id.asc(),
    ).all()


def primary_cluster_id_for_instance(instance: PrometheusInstance) -> str | None:
    bindings = cluster_bindings_for_instance(instance, enabled_only=True)
    return bindings[0].asset_key if bindings else None
