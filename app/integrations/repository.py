from __future__ import annotations

from app.extensions.db import db
from app.models import Cluster
from app.models.integration import IntegrationInstance
from app.models.kubernetes import KubernetesConnection


def get_kubernetes_connection_by_cluster_id(cluster_id: str) -> KubernetesConnection | None:
    return KubernetesConnection.query.filter_by(cluster_id=cluster_id).first()


def get_cluster(cluster_id: str) -> Cluster | None:
    return db.session.get(Cluster, cluster_id)


def get_integration_record(integration_type: str, integration_instance_id: int):
    from app.integrations.registry import get_integration

    module = get_integration(integration_type)
    return module.get_record_for_canonical(int(integration_instance_id))


def integration_identity_exists(integration_type: str, name: str) -> bool:
    normalized = str(name or '').strip()
    if not normalized:
        return False
    return IntegrationInstance.query.filter_by(integration_type=integration_type, name=normalized).first() is not None
