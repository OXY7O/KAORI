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
