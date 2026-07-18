from __future__ import annotations

from app.models.prometheus import PrometheusBinding, PrometheusInstance

KUBERNETES_CLUSTER_SCOPE = 'kubernetes_cluster'


def resolve_instance_for_cluster(cluster_id: str) -> PrometheusInstance | None:
    return (
        PrometheusInstance.query.join(PrometheusBinding)
        .filter(
            PrometheusBinding.scope_type == KUBERNETES_CLUSTER_SCOPE,
            PrometheusBinding.scope_key == cluster_id,
            PrometheusBinding.enabled.is_(True),
            PrometheusInstance.enabled.is_(True),
        )
        .order_by(
            db_case_primary(),
            PrometheusBinding.priority.asc(),
            PrometheusBinding.id.asc(),
        )
        .first()
    )


def db_case_primary():
    from sqlalchemy import case
    return case((PrometheusBinding.binding_role == 'primary', 0), else_=1)
