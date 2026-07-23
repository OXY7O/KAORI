from __future__ import annotations

from app.extensions import db
from app.models import Cluster
from app.models.integration import IntegrationInstance
from app.models.kubernetes import KubernetesConnection


def get_kubernetes_connection_by_cluster_id(cluster_id: str) -> KubernetesConnection | None:
    return KubernetesConnection.query.filter_by(cluster_id=cluster_id).first()


def get_cluster(cluster_id: str) -> Cluster | None:
    return db.session.get(Cluster, cluster_id)


def get_provider_record(provider_type: str, provider_record_id: int):
    from app.integrations.registry import get_integration

    module = get_integration(provider_type)
    return module.instance_loader(int(provider_record_id))


def provider_identity_exists(provider_type: str, name: str) -> bool:
    normalized = str(name or '').strip()
    if not normalized:
        return False
    return IntegrationInstance.query.filter_by(provider_type=provider_type, name=normalized).first() is not None
