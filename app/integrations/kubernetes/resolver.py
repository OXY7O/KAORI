from __future__ import annotations

from dataclasses import dataclass

from app.integrations.resolver import provider_record, resolve_integration
from app.models.cluster import Cluster
from app.models.kubernetes import KubernetesConnection

KUBERNETES_ASSET = 'kubernetes_cluster'


@dataclass(frozen=True, slots=True)
class KubernetesAssetRuntime:
    cluster: Cluster
    connection: KubernetesConnection


def resolve_kubernetes_for_cluster(cluster: Cluster | str) -> KubernetesAssetRuntime | None:
    cluster_obj = cluster if isinstance(cluster, Cluster) else Cluster.query.get(str(cluster))
    if cluster_obj is None:
        return None
    resolution = resolve_integration(
        integration_type='container_orchestrator',
        asset_type=KUBERNETES_ASSET,
        asset_key=cluster_obj.id,
        required_capabilities=(),
    )
    selected = resolution.selected
    if selected is None:
        return None
    connection = provider_record(selected.instance)
    if not isinstance(connection, KubernetesConnection):
        return None
    return KubernetesAssetRuntime(cluster_obj, connection)


def connection_for_cluster(cluster: Cluster) -> KubernetesConnection:
    runtime = resolve_kubernetes_for_cluster(cluster)
    if runtime is None:
        raise RuntimeError(f'No canonical Kubernetes connection is bound to cluster {cluster.id}.')
    return runtime.connection


def kubeconfig_for_cluster(cluster: Cluster) -> str:
    connection = connection_for_cluster(cluster)
    if not connection.kubeconfig:
        raise RuntimeError(f'Canonical Kubernetes connection for cluster {cluster.id} has no kubeconfig.')
    return connection.kubeconfig


def server_for_cluster(cluster: Cluster) -> str:
    return connection_for_cluster(cluster).server or ''


def tls_policy_for_cluster(cluster: Cluster) -> tuple[bool, bool]:
    connection = connection_for_cluster(cluster)
    return bool(connection.verify_ssl), bool(connection.allow_weak_tls)
