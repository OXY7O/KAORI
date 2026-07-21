"""Kubernetes API discovery contracts exposed through the integration boundary."""

from app.integrations.kubernetes.compatibility import (
    ApiCandidate,
    FeatureContract,
    KubernetesDiscovery,
    list_cluster_resource,
)

__all__ = ['ApiCandidate', 'FeatureContract', 'KubernetesDiscovery', 'list_cluster_resource']
