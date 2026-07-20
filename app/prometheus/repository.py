from __future__ import annotations

from app.integrations.resolver import provider_record, resolve_integration
from app.models.prometheus import PrometheusInstance

KUBERNETES_CLUSTER_SCOPE = 'kubernetes_cluster'


def resolve_instance_for_cluster(
    cluster_id: str,
    *,
    required_capabilities: tuple[str, ...] = (),
) -> PrometheusInstance | None:
    resolution = resolve_integration(
        provider_type='prometheus',
        asset_type=KUBERNETES_CLUSTER_SCOPE,
        asset_key=cluster_id,
        required_capabilities=required_capabilities,
    )
    selected = resolution.selected
    if selected is None:
        return None
    record = provider_record(selected.instance)
    return record if isinstance(record, PrometheusInstance) else None


def get_instance(instance_id: int) -> PrometheusInstance | None:
    return PrometheusInstance.query.filter_by(id=instance_id).first()


def list_instances() -> list[PrometheusInstance]:
    return PrometheusInstance.query.order_by(
        PrometheusInstance.created_at.asc(),
        PrometheusInstance.id.asc(),
    ).all()


def cluster_bindings_for_instance(
    instance: PrometheusInstance,
    *,
    enabled_only: bool = False,
):
    """Return managed-cluster bindings used by Prometheus administration views.

    Management pages include disabled bindings so lifecycle actions never hide a
    blocker. Runtime resolution can request enabled bindings explicitly.
    """
    from app.models.integration import IntegrationBinding

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
